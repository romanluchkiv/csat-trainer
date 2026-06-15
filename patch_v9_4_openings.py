"""
One-shot patch for v9.4 — rewrites Case 2 opening message to include
an accident + ~7h delay scenario, so the case cleanly qualifies for
a full refund under safety policy (no ambiguity).

Also removes "I want to speak to a manager / supervisor" demands from
all 4 case openings, per real 12Go SOP (managers are not part of the
customer-facing escalation path in this simulator).

Run once:
    python patch_v9_4_openings.py
"""
import json
import re
from pathlib import Path

CASES = Path('cases')

# Case 2 — Egypt safety. New opening: accident + ~7h delay, even stronger safety claim.
CASE_2_OPENING = (
    "Hello. I want to file a serious complaint about our trip from Hurghada to Sharm El Sheikh "
    "with Star Bus Egypt. We were involved in an accident on the highway — the driver had been "
    "smoking and texting on his phone the entire trip, driving at 145 km/h with headlights off "
    "on blind curves. He side-swiped another vehicle around 2am. Thankfully nobody was seriously "
    "injured, but we were stuck on the roadside for almost 7 hours waiting for a replacement bus. "
    "We arrived at our hotel completely exhausted and traumatized, hours after our scheduled "
    "arrival time. To make it worse, my grandfather's WWII-era Ruksac (1939) was damaged — torn "
    "strap and bent frame — from luggage being thrown around during the impact. We were terrified "
    "for our lives the entire trip even before the crash. We paid over 100€ for this service and "
    "this is the worst transport experience of our lives. I want a full refund immediately and "
    "compensation for the irreplaceable Ruksac. If this isn't resolved fairly I'm filing a "
    "dispute with our credit card company and posting detailed reviews everywhere."
)

# Regex to detect "I want to speak to / get me / put me through to a manager / supervisor"
MANAGER_PATTERNS = [
    re.compile(r'\bI (?:want|need|demand) (?:to speak (?:to|with)|a)? ?(?:a )?(supervisor|manager)\b', re.IGNORECASE),
    re.compile(r'\bput me through (?:to )?(?:a )?(supervisor|manager)\b', re.IGNORECASE),
    re.compile(r'\bget me (?:a |your )?(supervisor|manager)\b', re.IGNORECASE),
    re.compile(r'\btransfer me to (?:a )?(supervisor|manager)\b', re.IGNORECASE),
]


def clean_manager_demands(text):
    """Soft-remove manager/supervisor escalation demands. Keep the rest of the message."""
    for pat in MANAGER_PATTERNS:
        text = pat.sub('', text)
    # Clean up double spaces / orphan punctuation
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' +([.,!?])', r'\1', text)
    text = re.sub(r'\.\s*\.', '.', text)
    return text.strip()


def patch_case_2():
    path = CASES / 'case_636721.json'
    if not path.exists():
        print(f'  Skipped: {path} not found')
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    old = data.get('opening_message', '')
    data['opening_message'] = CASE_2_OPENING
    # Also update situation summary if present
    if 'customer_profile' in data:
        old_sit = data['customer_profile'].get('situation', '')
        if 'accident' not in old_sit.lower():
            data['customer_profile']['situation'] = (
                'Customer was involved in a highway accident with Star Bus Egypt operator '
                '(Hurghada → Sharm El Sheikh). Driver was smoking and texting at 145 km/h with '
                'lights off; side-swiped another vehicle around 2am, resulting in ~7-hour delay '
                'roadside. Customer was terrified, arrived exhausted hours late. Grandfather\'s '
                'WWII-era Ruksac was damaged in the impact (torn strap, bent frame). '
                'Demands full refund + luggage compensation. This is a clear safety failure '
                'qualifying for full refund under safety policy.'
            )
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'  case_636721.json (Case 2): opening rewritten with accident + 7h delay scenario')


def patch_other_openings():
    for filename in ['case_973250.json', 'case_748911.json', 'case_784988.json']:
        path = CASES / filename
        if not path.exists():
            print(f'  Skipped: {path} not found')
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        old = data.get('opening_message', '')
        cleaned = clean_manager_demands(old)
        if cleaned != old:
            data['opening_message'] = cleaned
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f'  {filename}: manager/supervisor demands removed from opening')
        else:
            print(f'  {filename}: no manager/supervisor demands in opening (already clean)')


def main():
    print('v9.4 — Case 2 opening rewrite + manager demand cleanup')
    print()
    patch_case_2()
    patch_other_openings()
    print()
    print('Done.')


if __name__ == '__main__':
    main()
