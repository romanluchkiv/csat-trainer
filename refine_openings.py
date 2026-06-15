"""
One-off script to refine the customer's opening_message in all cases.

Goal: make the opening complaint more realistic by removing direct brags
about having evidence/photos/screenshots. The customer should describe what
happened without immediately advertising 'I have photos'. The agent should
prompt for evidence as part of the workflow.

Usage:
    python3 refine_openings.py
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


REFINE_PROMPT = """Rewrite the customer's opening_message for a CSAT training simulator.

CURRENT opening_message:
{opening}

CASE CONTEXT:
{case_situation}

PROBLEMS WITH THE CURRENT OPENING:
- It explicitly mentions photos/evidence/screenshots/timestamps the customer claims to have. This makes the LLM-customer in the simulation start pushing the agent about evidence immediately, instead of letting the agent ask for it naturally as part of the workflow.

REWRITE THE OPENING SUCH THAT:
1. The customer describes the bad experience clearly and emotionally (this part should be preserved).
2. The customer does NOT brag about having photos, videos, screenshots, timestamps, or other evidence. Just describe what happened.
3. The customer can mention wanting a refund, threatening reviews/complaints — that's natural.
4. Length: keep similar length to the original. The opening_message is special — it's allowed to be longer (real complaints often are). Don't shorten too aggressively.
5. Keep the customer's voice and quirks (any typos, informal language, etc.) — it should still sound like the same real human, just without the evidence-brag.
6. Keep the original language (English, mixed English/Spanish, whatever).

OUTPUT: Return ONLY valid JSON, no preamble:

{{
  "opening_message": "The rewritten opening message string."
}}"""


def refine_case(client, case_path: Path) -> bool:
    print(f"\n--- {case_path.name} ---")
    try:
        case = json.loads(case_path.read_text(encoding='utf-8'))
        current = case.get('opening_message', '')
        situation = case.get('customer_profile', {}).get('situation', '')

        prompt = REFINE_PROMPT.format(opening=current, case_situation=situation)
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

        result = json.loads(text)
        new_opening = result['opening_message']
        case['opening_message'] = new_opening
        case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f"  BEFORE ({len(current)} chars): {current[:150]}...")
        print(f"  AFTER  ({len(new_opening)} chars): {new_opening[:150]}...")
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
