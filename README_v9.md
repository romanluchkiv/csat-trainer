# CSAT Trainer — v9 Upgrade Notes

## What's new in v9

### Quality fixes (the main reason for this release)

1. **JSON crash fixed** — JUDGE now uses Anthropic structured output (tool_use). The "Unterminated string" class of errors is gone entirely.

2. **Agent view = clean** — final CSAT shows just: score, customer comment, coach verdict (1 paragraph), emotional ack, strengths, gaps. The detailed manager-style breakdown (per-turn, promises, diagnostics) is behind a toggle "Show detailed manager view".

3. **Emotional Acknowledgment block** — always visible. Green ✅ if agent opened with empathy, red ❌ if process-first.

4. **Internal notes split by team** — start an internal note with "Dear IT" → goes to IT LLM (checks logs, doesn't need screenshots). Start with "Dear Ops" → goes to Ops LLM (operator/refund issues). Each team has its own context and policy knowledge.

5. **IT team prompt added** — for payment errors, broken pages, double-charges. Knows it can check logs without screenshots.

6. **Ops auto-knows context** — booking reference, route, pickup/dropoff, confirmation type. No more hallucinated "could you provide the booking reference?" when the agent shouldn't need to repeat it.

7. **Ops timing is context-aware** — urgent <24h cases get hours-not-days responses. Refund investigations still use 3-5 business days realistic ETA.

8. **Ops knows policy** — unconfirmed bookings = automatic 100% refund (clause 8). Won't ask "should I push for confirmation or also request refund?" — it knows.

9. **Customer ends conversation properly** — if satisfied, customer writes a short closing and `[END_CONVERSATION]`. No more dragging with nitpicky "how many days is shortly?" follow-ups after refund confirmation.

10. **Booking Info sidebar shows** — BID, route, pickup address (with hotel for door-to-door), dropoff address (with hotel for door-to-door), confirmation type (instant/manual), status, refund policy.

11. **Color-coded messages** — internal notes (agent + Ops + IT) have yellow background like Zendesk. Customer + public agent replies stay neutral.

12. **Attachment placeholder fix** — uses `st.info()` instead of raw HTML. Cmd+C now copies plain text, not HTML markup.

13. **Agent name dropdown** — pick from `agent_roster.csv` instead of typing your name (no more typos in identity).

14. **12Go branding** — green header badge with brand color #5DBE3F.

15. **ToU clauses enforced in judge** — if `applicable_tou_clauses` is non-empty and the agent makes a refund/policy commitment without citing them, the judge flags it as a TYPE B broken promise.

16. **max_turns: 7 for Case 3** — auto-corrected by the enrichment script.

---

## Installation

### Step 1 — Stop the running Streamlit (if any)
In your terminal where `streamlit run trainer.py` is running, press **Ctrl+C**.

### Step 2 — Backup your current setup (optional but recommended)
```bash
cd ~/Desktop
cp -r csat_trainer csat_trainer_v8_backup
```

### Step 3 — Replace these 3 files with the v9 versions
Inside `~/Desktop/csat_trainer/`:
- `prompts.py` ← replace with v9
- `trainer.py` ← replace with v9
- `enrich_v9_metadata.py` ← **NEW FILE**, add it
- `agent_roster.csv` ← **NEW FILE**, add it (edit emails to match your team)

### Step 4 — Edit `agent_roster.csv` with your team's emails
Format: `email,Full Name` — one per line.

```
roman.luchkiv@12go.asia,Roman Luchkiv
volodymyr.k@12go.asia,Volodymyr Krokhmalnyi
karn@12go.asia,Karn
```

### Step 5 — Run the enrichment script ONCE to update your case JSONs
This adds the new v9 fields (customer_name, BID, pickup/dropoff, confirmation_type) to your existing 4 cases.

```bash
cd ~/Desktop/csat_trainer
source venv/bin/activate
python enrich_v9_metadata.py
```

You'll see output like:
```
--- case_973250.json ---
  Enriched fields: customer_name, booking_id, pickup_address, dropoff_address, confirmation_type, it_context
    customer_name: Maria Garcia
    booking_id:    BID 7234891
    pickup:        Cebu South Bus Terminal
    dropoff:       SM Mall of Asia, Pasay
    confirmation:  instant
  Saved.

--- case_748911.json ---
  Applied fixes: max_turns=7
  Enriched fields: ...
  Saved.
```

The script is **safe to re-run** — it only adds missing fields. If you want to regenerate everything, use `--force`.

### Step 6 — Launch v9
```bash
streamlit run trainer.py
```

Open http://localhost:8501.

### Step 7 — Verify it works
- Pick your name from the dropdown (sidebar)
- Pick a case
- Click Start
- The Booking Info sidebar should now show BID, pickup, dropoff, confirmation type
- Try a public reply — coach feedback appears
- Try an internal note starting with "Dear IT" → IT team replies (look for blue left-border)
- Try an internal note starting with "Dear Ops" → Ops team replies (yellow/gold left-border)
- Complete a session — the final CSAT view should be clean (just verdict + strengths/gaps + emotional ack), with a "Show detailed manager view" toggle at the bottom

---

## Troubleshooting

**"No cases found"**
→ Your /cases folder is empty. v9 reuses your existing case JSONs. Make sure they're still there.

**Enrichment script fails on one case**
→ Check the error. Usually it's a network blip — re-run, only failed cases will be retried.

**Internal note isn't routing to IT**
→ Make sure your note starts with "Dear IT" (case-insensitive). If you forget the greeting, it defaults to Ops. You can also type "Hi IT," or "To IT team:" — the router checks the first 80 chars.

**CSAT still crashes**
→ Shouldn't happen — tool_use is enforced server-side. If it does, the fallback verdict (with explanation) appears. Take a screenshot and we'll investigate.

**Cmd+C still copies HTML**
→ The attachment placeholder is now `st.info()` (plain text). If it still copies HTML, your case JSON might have raw HTML in `opening_message` — let me know which case.

**Agent dropdown is short**
→ Edit `agent_roster.csv` and add more lines. Restart Streamlit.

---

## Files in v9

| File | Changed in v9? | What it does |
|---|---|---|
| `prompts.py` | ✅ Rewritten | All LLM prompts + tool_use schema for judge |
| `trainer.py` | ✅ Rewritten | Streamlit UI, structured judge call, IT/Ops routing |
| `enrich_v9_metadata.py` | ✅ NEW | One-time script to add v9 fields to existing cases |
| `agent_roster.csv` | ✅ NEW | Editable list of agents (email + name) |
| `analyze_ticket.py` | — | Unchanged. Still works for generating new cases. |
| `anonymize.py` | — | Unchanged. |
| `refine_personalities.py` | — | Unchanged. |
| `refine_openings.py` | — | Unchanged. |
| `enrich_booking_facts.py` | — | Unchanged. Still useful for new cases. |
| `enrich_operator.py` | — | Unchanged. |
| `enrich_ops_context.py` | — | Unchanged. |
| `enrich_tou_clauses.py` | — | Unchanged. Existing tou clauses preserved. |
| `cases/case_*.json` | ✅ Enriched | New fields added by `enrich_v9_metadata.py` |

---

## What's NOT in v9 (planned for FINAL release)

- Multi-user deployment (Streamlit Cloud / Railway)
- Email-based auth
- Sequential case flow (Case 1 → 2 → 3 → 4 without menu)
- Onboarding flow (terms, rules, time estimate)
- Final aggregate score on 100-scale across all 4 cases
- "Contact manager for training" CTA
- Manager dashboard
- Corporate API key
- Persistent storage in Google Sheet

These come after v9 is validated. v9 is the quality milestone before scaling.

---

## Cost estimate per session

With structured output (tool_use):
- Per turn: ~3500 input + 400 output tokens (coach) + ~800 customer
- Per session (5-8 turns): ~$0.15-0.30
- Per agent per case: ~$0.20 average

For 25 people × 4 cases each: ~$20 one-time + cost of retries.

---

## Next steps

1. Install v9 (steps above)
2. Run all 4 cases yourself, twice
3. Note any issues — especially: any crash, weird Ops/IT response, customer not ending conversation, ToU clauses not referenced
4. We iterate based on findings
5. Once stable → start planning FINAL multi-user release

Test thoroughly. Take screenshots. We'll iterate from there.
