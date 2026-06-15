"""
Ticket analyzer.

Usage:
    python analyze_ticket.py 123456 123457 123458 123459

For each ticket ID:
1. Fetches ticket from Zendesk (comments, satisfaction rating, requester)
2. Anonymizes PII
3. Sends to Claude with ANALYZER_PROMPT
4. Saves resulting training case to cases/case_<id>.json

Requires .env with ZENDESK_* and ANTHROPIC_API_KEY set.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from anthropic import Anthropic

from anonymize import anonymize_ticket_data
from prompts import ANALYZER_PROMPT


load_dotenv()

ZENDESK_SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN')
ZENDESK_EMAIL = os.getenv('ZENDESK_EMAIL')
ZENDESK_API_TOKEN = os.getenv('ZENDESK_API_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

CASES_DIR = Path(__file__).parent / 'cases'
CASES_DIR.mkdir(exist_ok=True)


def zendesk_auth():
    return (f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)


def fetch_ticket(ticket_id: int) -> dict:
    """Fetch ticket details from Zendesk."""
    base = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

    # Ticket
    r = requests.get(f"{base}/tickets/{ticket_id}.json", auth=zendesk_auth())
    r.raise_for_status()
    ticket = r.json()['ticket']

    # Comments (the full conversation)
    r = requests.get(f"{base}/tickets/{ticket_id}/comments.json", auth=zendesk_auth())
    r.raise_for_status()
    comments = r.json()['comments']

    # Requester (customer)
    requester_id = ticket['requester_id']
    r = requests.get(f"{base}/users/{requester_id}.json", auth=zendesk_auth())
    r.raise_for_status()
    requester = r.json()['user']

    # User cache for resolving comment authors
    user_cache = {requester_id: requester}

    def resolve_author(author_id: int) -> dict:
        if author_id not in user_cache:
            try:
                r = requests.get(f"{base}/users/{author_id}.json", auth=zendesk_auth())
                r.raise_for_status()
                user_cache[author_id] = r.json()['user']
            except Exception:
                user_cache[author_id] = {'role': 'unknown', 'name': 'Unknown'}
        return user_cache[author_id]

    # Satisfaction rating (CSAT)
    csat_score = None
    csat_comment = None
    if ticket.get('satisfaction_rating'):
        rating = ticket['satisfaction_rating']
        if isinstance(rating, dict):
            csat_score = rating.get('score')
            csat_comment = rating.get('comment')

    # Build message list
    messages = []
    for c in comments:
        author = resolve_author(c['author_id'])
        role = author.get('role', 'unknown')
        if author['id'] == requester_id:
            author_role = 'customer'
        elif role in ('agent', 'admin'):
            author_role = 'agent'
        else:
            author_role = role
        messages.append({
            'author_role': author_role,
            'body': c.get('plain_body') or c.get('body', ''),
            'created_at': c.get('created_at'),
            'public': c.get('public', True),
        })

    return {
        'ticket_id': ticket_id,
        'subject': ticket.get('subject', ''),
        'customer_name': requester.get('name', 'Customer'),
        'csat_score': csat_score,
        'csat_comment': csat_comment,
        'messages': messages,
    }


def analyze_with_claude(client: Anthropic, anonymized_ticket: dict) -> dict:
    """Send anonymized ticket to Claude for training-scenario extraction."""
    ticket_json = json.dumps(anonymized_ticket, ensure_ascii=False, indent=2)
    prompt = ANALYZER_PROMPT.replace('{ticket_json}', ticket_json)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = response.content[0].text.strip()
    # Strip possible markdown fences
    if text.startswith('```'):
        text = text.split('```', 2)[1]
        if text.startswith('json'):
            text = text[4:]
        text = text.strip()
        if text.endswith('```'):
            text = text[:-3].strip()

    return json.loads(text)


def process_ticket(ticket_id: int, client: Anthropic) -> Optional[Path]:
    print(f"\n--- Ticket {ticket_id} ---")
    try:
        print("  Fetching from Zendesk...")
        ticket = fetch_ticket(ticket_id)
        print(f"  Got {len(ticket['messages'])} messages, CSAT: {ticket.get('csat_score')}")

        print("  Anonymizing PII...")
        anon = anonymize_ticket_data(ticket)

        print("  Sending to Claude for analysis...")
        case = analyze_with_claude(client, anon)
        case['source_ticket_id'] = ticket_id
        case['source_csat_score'] = ticket.get('csat_score')

        out_path = CASES_DIR / f'case_{ticket_id}.json'
        out_path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  Saved: {out_path}")
        print(f"  Case title: {case.get('case_title')}")
        return out_path
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticket_ids', nargs='+', type=int, help='Zendesk ticket IDs to analyze')
    args = parser.parse_args()

    if not all([ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN, ANTHROPIC_API_KEY]):
        print("ERROR: Missing env vars. Copy .env.example to .env and fill in.")
        sys.exit(1)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    results = []
    for tid in args.ticket_ids:
        results.append(process_ticket(tid, client))

    successful = [r for r in results if r]
    print(f"\nDone. {len(successful)}/{len(args.ticket_ids)} cases generated.")


if __name__ == '__main__':
    main()
