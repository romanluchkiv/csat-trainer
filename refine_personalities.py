"""
One-off script to rewrite personality_notes in all cases to be more
realistic and behavior-conditional ('uses X when frustrated' not 'always X').

Usage:
    python3 refine_personalities.py
"""
import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic


load_dotenv()
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

CASES_DIR = Path(__file__).parent / 'cases'


REFINE_PROMPT = """Rewrite the customer's personality_notes for a CSAT training simulator.

The CURRENT personality_notes tend to make the LLM-customer behave unrealistically:
- Writes 200+ word messages with bullet lists in every reply
- Uses CAPS LOCK constantly instead of occasionally
- Switches to foreign language in every message instead of sparingly
- Uses legal/corporate language like 'written commitment' and 'consumer protection laws'
- Repeats the same threats in every message
- Pre-conditions every action with multiple requirements

REWRITE the personality_notes so the LLM understands:
- This is a real human who writes SHORT messages most of the time (1-3 sentences typical)
- Behaviors should be CONDITIONAL — 'uses caps WHEN very frustrated' not 'uses caps'
- Foreign language is for one peak moment, not every message
- Threats are mentioned once, not in every turn
- The customer should sound like a regular person who happens to be upset, not like a litigation lawyer

CURRENT CASE:
{case_json}

OUTPUT: Return ONLY valid JSON with the new personality_notes string. Keep it 2-4 sentences. Be specific about WHEN behaviors trigger.

{{
  "personality_notes": "Rewritten personality_notes that are realistic and conditional. 2-4 sentences."
}}"""


def refine_case(client, case_path: Path) -> bool:
    print(f"\n--- {case_path.name} ---")
    try:
        case = json.loads(case_path.read_text(encoding='utf-8'))
        current = case.get('customer_profile', {}).get('personality_notes', '')
        print(f"  BEFORE: {current[:100]}...")

        prompt = REFINE_PROMPT.replace(
            '{case_json}', json.dumps(case, ensure_ascii=False, indent=2)
        )
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
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

        result = json.loads(text)
        new_notes = result['personality_notes']
        case['customer_profile']['personality_notes'] = new_notes
        case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f"  AFTER:  {new_notes}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY missing in .env")
        sys.exit(1)

    paths = sorted(CASES_DIR.glob('case_*.json'))
    if not paths:
        print("No case files found.")
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    ok = sum(refine_case(client, p) for p in paths)
    print(f"\nDone. {ok}/{len(paths)} cases refined.")


if __name__ == '__main__':
    main()
