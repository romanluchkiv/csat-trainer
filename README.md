# 12Go CSAT Trainer — Setup Guide

Interactive training tool: agents practice real customer scenarios with an LLM-simulated customer, get per-turn coaching feedback, and a final CSAT verdict.

## Prerequisites

- Python 3.10+ on your machine
- Anthropic API key (console.anthropic.com)
- Zendesk API token + email with read access to tickets

## Step 1: Install (one-time, ~3 min)

```bash
# In a new terminal, go to the project folder
cd csat_trainer

# Create a virtual env (recommended, keeps deps isolated)
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure

```bash
# Copy the template
cp .env.example .env

# Open .env in your editor and fill in:
# - ANTHROPIC_API_KEY
# - ZENDESK_SUBDOMAIN (e.g. "12go" if your URL is 12go.zendesk.com)
# - ZENDESK_EMAIL (your work email)
# - ZENDESK_API_TOKEN
```

## Step 3: Test Zendesk + Anthropic connection

```bash
# Quick anonymizer test (no API needed)
python anonymize.py
# Should print sample text with emails/phones replaced

# Test by analyzing ONE ticket first (uses ~$0.10)
python analyze_ticket.py <your_ticket_id>
```

If it works, you'll see `cases/case_<id>.json` appear. Open it — check the analysis looks reasonable.

## Step 4: Generate all 4 cases

```bash
python analyze_ticket.py 111111 222222 333333 444444
```

Replace with your 4 real ticket IDs. Each takes ~30-60 sec. Total cost: ~$0.40.

## Step 5: Run the trainer

```bash
streamlit run trainer.py
```

Opens in your browser at http://localhost:8501

## What to expect on the first run-through

1. Enter your name in the sidebar
2. Pick a case
3. Click "Start session"
4. Read the case context (top panel)
5. Read the customer's opening message
6. Type your reply
7. Coach feedback appears, then customer's next message
8. Continues until 5 turns OR customer ends the conversation
9. Final CSAT verdict + strengths/gaps summary
10. Session logged to `logs/sessions.csv`

## Troubleshooting

**"No cases found"** → run `analyze_ticket.py` first.

**Zendesk 401 error** → check email/token. Token comes from Zendesk Admin → Apps & Integrations → APIs → Zendesk API.

**Customer responses in wrong language** → check the case JSON file, `case_language` field. Edit manually if Claude misidentified.

**Want to tweak the customer's personality** → edit `cases/case_<id>.json` directly. The `customer_profile.personality_notes` field is the main lever.

## Costs (rough estimates)

- Analyzing 4 tickets: ~$0.50 total
- One training session (5 turns + verdict): ~$0.15-0.30
- 30 agents × 4 sessions/month = ~$30-50/month

## Files in this project

| File | What it does |
|---|---|
| `anonymize.py` | Strips emails/phones/booking refs before sending to LLM |
| `analyze_ticket.py` | Fetches Zendesk ticket → Claude analyzes → saves case JSON |
| `prompts.py` | All LLM prompts (analyzer, customer, coach, judge) |
| `trainer.py` | Streamlit UI for agents |
| `cases/` | Generated training scenarios |
| `logs/sessions.csv` | All training session results (for tracking team progress) |
