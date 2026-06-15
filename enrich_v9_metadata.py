"""
Enrich existing case JSONs with v9 metadata fields.

Adds (where missing):
- customer_name (fictional)
- booking_id (e.g. 'BID 7234891')
- pickup_address (with hotel name for door-to-door)
- dropoff_address (with hotel name for door-to-door)
- confirmation_type ('instant' or 'manual')
- it_context (for technical-error cases only)

Also fixes known bugs:
- case_748911.json max_turns: 8 → 7 (Case 3 Vietnam)

Usage:
    python enrich_v9_metadata.py
    python enrich_v9_metadata.py --case case_748911.json   # single case
    python enrich_v9_metadata.py --force                   # overwrite existing fields
"""
import os
import sys
import json
import argparse
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from prompts import V9_METADATA_ENRICHMENT_PROMPT


load_dotenv()
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

CASES_DIR = Path(__file__).parent / 'cases'

# Fields v9 adds
V9_FIELDS = ['customer_name', 'booking_id', 'pickup_address',
             'dropoff_address', 'confirmation_type', 'it_context']

# Known per-case fixes
PER_CASE_FIXES = {
    'case_636721.json': {
        'max_turns': 7,  # Case 2 — Egypt safety (v9.1: was 8, should be 7)
        '_booking_facts_departure_date': '{{TODAY_PLUS_DAYS_7}}',  # v9.2: future booking, 1 week out
    },
    'case_748911.json': {
        'max_turns': 7,  # Case 3 — Vietnam wrong dropoff
        '_booking_facts_departure_date': '{{YESTERDAY}}',  # v9.2: trip already happened yesterday
    },
    'case_973250.json': {
        '_booking_facts_departure_date': '{{TODAY_PLUS_DAYS_5}}',  # v9.2: Case 1 — future booking, ~5 days out
    },
    'case_784988.json': {
        '_booking_facts_departure_date': '{{TOMORROW_PLUS_HOURS_18}}',  # v9.2: Case 4 — urgent <24h, tomorrow 18:00
    },
}


def enrich_case(client, case_data, force=False):
    """Ask Claude to propose v9 metadata for this case."""
    # Skip if already has all fields and not forcing
    missing = [f for f in V9_FIELDS if f not in case_data or case_data.get(f) in (None, '')]
    if not missing and not force:
        return case_data, False, []

    case_json = json.dumps(case_data, ensure_ascii=False, indent=2)
    prompt = V9_METADATA_ENRICHMENT_PROMPT.format(case_json=case_json)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith('```'):
        text = text.split('```', 2)[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()
        if text.endswith('```'):
            text = text[:-3].strip()

    proposed = json.loads(text)

    changes = []
    for field in V9_FIELDS:
        if force or field not in case_data or case_data.get(field) in (None, ''):
            new_val = proposed.get(field)
            if new_val is not None:
                case_data[field] = new_val
                changes.append(field)
    return case_data, True, changes


def apply_per_case_fixes(filename, case_data):
    """Apply hardcoded per-case fixes (e.g. max_turns corrections, departure date tokens)."""
    fixes = PER_CASE_FIXES.get(filename, {})
    applied = []
    for key, val in fixes.items():
        # v9.2: special prefix _booking_facts_<field> writes into booking_facts dict
        if key.startswith('_booking_facts_'):
            sub_key = key[len('_booking_facts_'):]
            bf = case_data.setdefault('booking_facts', {})
            if bf.get(sub_key) != val:
                bf[sub_key] = val
                applied.append(f'booking_facts.{sub_key}={val}')
            continue
        if case_data.get(key) != val:
            case_data[key] = val
            applied.append(f'{key}={val}')

    # v9.4: strip 'BID ' prefix from booking_id values (was duplicated in UI)
    bid = case_data.get('booking_id', '')
    if isinstance(bid, str) and bid.upper().startswith('BID '):
        case_data['booking_id'] = bid[4:].strip()
        applied.append(f'booking_id stripped to {case_data["booking_id"]}')

    return applied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', help='Single case file (e.g. case_973250.json)')
    parser.add_argument('--force', action='store_true', help='Overwrite existing v9 fields')
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print('ERROR: ANTHROPIC_API_KEY missing in .env')
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    if args.case:
        files = [CASES_DIR / args.case]
    else:
        files = sorted(CASES_DIR.glob('case_*.json'))

    if not files:
        print('No case files found in /cases')
        sys.exit(1)

    for path in files:
        if not path.exists():
            print(f'Skip: {path.name} not found')
            continue

        print(f'\n--- {path.name} ---')
        case_data = json.loads(path.read_text(encoding='utf-8'))

        # 1. Per-case hardcoded fixes (max_turns etc.)
        applied = apply_per_case_fixes(path.name, case_data)
        if applied:
            print(f'  Applied fixes: {", ".join(applied)}')

        # 2. v9 metadata enrichment
        try:
            case_data, enriched, changes = enrich_case(client, case_data, force=args.force)
            if enriched:
                print(f'  Enriched fields: {", ".join(changes) if changes else "(none new)"}')
                print(f'    customer_name: {case_data.get("customer_name")}')
                print(f'    booking_id:    {case_data.get("booking_id")}')
                print(f'    pickup:        {case_data.get("pickup_address")}')
                print(f'    dropoff:       {case_data.get("dropoff_address")}')
                print(f'    confirmation:  {case_data.get("confirmation_type")}')
            else:
                print('  All v9 fields already present (use --force to overwrite)')
        except Exception as e:
            print(f'  ERROR enriching: {e}')
            if not applied:
                continue  # don't save if nothing changed and enrichment failed

        # Save
        path.write_text(json.dumps(case_data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  Saved.')

    print('\nDone.')


if __name__ == '__main__':
    main()
