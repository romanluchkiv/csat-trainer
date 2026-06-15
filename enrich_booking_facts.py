"""
Enrich existing cases with the 'booking_facts' field.

Usage:
    python3 enrich_booking_facts.py
    # processes all case_*.json files in cases/

Or specific files:
    python3 enrich_booking_facts.py cases/case_973250.json
"""
import os
import sys
import json
import argparse
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from prompts import BOOKING_FACTS_ENRICHMENT_PROMPT


load_dotenv()
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

CASES_DIR = Path(__file__).parent / 'cases'


def enrich_case(client, case_path: Path) -> bool:
    print(f"\n--- {case_path.name} ---")
    try:
        case = json.loads(case_path.read_text(encoding='utf-8'))
        if 'booking_facts' in case:
            print('  Already has booking_facts, skipping')
            return True

        prompt = BOOKING_FACTS_ENRICHMENT_PROMPT.replace(
            '{case_json}', json.dumps(case, ensure_ascii=False, indent=2)
        )
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
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

        facts = json.loads(text)
        case['booking_facts'] = facts
        case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f"  Enriched.")
        print(f"  Route: {facts.get('route')}")
        print(f"  Status: {facts.get('booking_status')}")
        print(f"  Policy: {facts.get('refund_policy')}")
        print(f"  Country: {facts.get('customer_country')}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*', help='Specific case JSON files. Defaults to all in cases/')
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY missing in .env")
        sys.exit(1)

    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = sorted(CASES_DIR.glob('case_*.json'))

    if not paths:
        print("No case files found.")
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    ok = sum(enrich_case(client, p) for p in paths)
    print(f"\nDone. {ok}/{len(paths)} cases enriched.")


if __name__ == '__main__':
    main()
