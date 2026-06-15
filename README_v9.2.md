# CSAT Trainer — v9.2 (patch on top of v9.1)

## What's NEW in v9.2

Only fixes Roman explicitly requested today. Nothing else changed.

### Coach/Judge rules added (prompts.py — JUDGE_SYSTEM_PROMPT)

The Judge tool now flags these SOP violations in `key_gaps`:

1. **Promised vs actually sent evidence.** If agent's internal note claims "photos received" / "attachments received" but no `[Attachments: ...]` marker exists in any prior customer turn → hallucinated evidence, gap.

2. **Reply length match.** Agent reply must match customer length. Customer 1-3 sentences → agent 1-3 sentences. Wall of text / bullets when customer wrote briefly = gap.

3. **Well-received before internal escalation.** When customer sends evidence (`[Attachments: ...]` marker), agent must send a brief public acknowledgment FIRST, then internal note. Going straight to internal = gap.

4. **No internal team names in public.** Agent must never mention "Ops", "Operations team", "IT team" in public replies. Use neutral phrasing ("our team", "the operator", "our partners"). Flag violations.

5. **No "auto-trigger" refund wording.** Agent must never write "refund triggers automatically" / "auto-process". Even under clause 8, CS processes refund manually. Use "I will process your refund" / "we will refund you".

6. **Promo code option.** For complaint cases (especially wrong drop-off under clause 4), agent may offer promo code as goodwill — before or instead of refund. Missing this opportunity is a minor gap.

### Real refund policy correction (prompts.py — REFUND_POLICY_RULES)

- **Clause 4 (wrong drop-off):** rewritten — 12Go refunds the EXTRA COSTS ONLY (Grab/taxi) at operator's expense. The ORIGINAL BOOKING is NOT refunded (trip happened, just to wrong drop-off). A PROMO CODE may be added as goodwill. The previous v9.1 wording over-promised "partial or full refund of original booking" — corrected.
- **Clause 8 (unconfirmed booking):** clarified that CS processes the refund manually. Removed wording "AUTOMATIC 100% refund" which implied a system trigger. Now: "100% refund. No operator approval needed. The CS agent processes the refund themselves."

### Ops/IT prompt fixes (prompts.py)

7. **OPS_TEAM_SYSTEM_PROMPT updated:**
   - Always addresses agent as "Dear CS" (not "Dear Roman" / first name).
   - For wrong-dropoff: suggests Grab refund + promo code, does NOT approve partial booking refund (the old behavior that gave 50% was inflated).
   - For unconfirmed: says "CS to process the refund", not "automatic refund".
   - Example Ops responses rewritten to match real 12Go policy.

8. **IT_TEAM_SYSTEM_PROMPT updated:**
   - Always addresses agent as "Dear CS".

### Wait button context-aware (trainer.py)

9. The Wait button now adapts to case urgency:
   - For cases with departure < 24 hours away, the button reads: **"⏳ Skip ahead — request Ops update now (urgent <24h)"** and simulates "a few hours" passing, not 5 business days.
   - For other cases (refund investigations), the original "5 business days" behavior is preserved.

### Dynamic departure dates (trainer.py + enrich_v9_metadata.py)

10. `departure_date` in case JSONs can now use dynamic tokens that resolve relative to the moment the agent opens the case:

   - `{{TODAY}}`, `{{TOMORROW}}`, `{{YESTERDAY}}`, `{{NOW}}`
   - `{{TODAY_PLUS_DAYS_N}}` — e.g. `{{TODAY_PLUS_DAYS_7}}`
   - `{{TODAY_MINUS_DAYS_N}}`
   - `{{TOMORROW_PLUS_HOURS_N}}` — e.g. `{{TOMORROW_PLUS_HOURS_18}}` for tomorrow 18:00

   The enrichment script writes these tokens into the 4 case JSONs:

   - **Case 1 (Philippines double booking)** → `{{TODAY_PLUS_DAYS_5}}` (future trip)
   - **Case 2 (Egypt safety)** → `{{TODAY_PLUS_DAYS_7}}` (future trip, 1 week out)
   - **Case 3 (Vietnam wrong dropoff)** → `{{YESTERDAY}}` (trip already happened)
   - **Case 4 (Frances unconfirmed)** → `{{TOMORROW_PLUS_HOURS_18}}` (urgent <24h)

   This means every agent who opens the simulator sees a realistic departure date relative to "now". No manual date updates needed before each rollout.

---

## What is NOT changed

Everything else in v9.1 remains: 12Go logo, font sizes, no live Coach feedback, yellow internal notes with dark text, CLIENT prompt rules (attachment marker, fact consistency), Case context block removal, etc.

---

## Installation

### Step 1 — Stop Streamlit
Ctrl+C in the terminal where it's running.

### Step 2 — Replace 3 files
Inside `~/Desktop/csat_trainer/`:
- Replace `trainer.py` with the v9.2 version
- Replace `prompts.py` with the v9.2 version
- Replace `enrich_v9_metadata.py` with the v9.2 version

`agent_roster.csv` and `12go_logo.jpg` stay as they are.

### Step 3 — Re-run enrichment to apply dynamic date tokens
```bash
cd ~/Desktop/csat_trainer
source venv/bin/activate
python enrich_v9_metadata.py
```

You should see lines like:
```
--- case_784988.json ---
  Applied fixes: booking_facts.departure_date={{TOMORROW_PLUS_HOURS_18}}
  Saved.
```

(if it says "All v9 fields already present" — that's fine, the date fix is still applied separately.)

### Step 4 — Launch
```bash
streamlit run trainer.py
```

### Step 5 — Verify
- Open Case 4 (Frances) — the **Departure** in Booking Information should show **tomorrow's date** (resolved from the token).
- Open Case 3 (Vietnam) — Departure should show **yesterday**.
- Case 1 and Case 2 should show **future dates** (5 and 7 days out).
- Wait button on Case 4 should read "Skip ahead — request Ops update now (urgent <24h)", not "5 business days".
- Ops/IT replies should start with "Dear CS".
- Ops should not mention "automatic refund" or 50% partial booking refunds.

---

## Files in v9.2

| File | Changed in v9.2? |
|---|---|
| `prompts.py` | ✅ Patched (Judge rules, refund policy, Ops/IT prompts) |
| `trainer.py` | ✅ Patched (date tokens, Wait button context-aware) |
| `enrich_v9_metadata.py` | ✅ Patched (date tokens per case) |
| `agent_roster.csv` | — unchanged |
| `12go_logo.jpg` | — unchanged (from v9.1) |

---

## Backlog after v9.2

Everything for **FINAL release**:
- Multi-user deploy (5 managers pilot → 20 agents)
- Email whitelist + role-based access (agent vs manager)
- Onboarding flow (email → terms → 4 cases sequentially)
- Per-case CSAT 1-5 + aggregate 0-100 final score
- CTA based on score ("Contact your manager for X hour training")
- Per-case Coach verdict shown ONLY at the very end (not between cases) — Vova's recommendation
- 45-min timer with "Submit early" option
- Persistent storage (Google Sheet)
- Manager dashboard
- Anti-cheat: stylistic AI-detection at session end
- Hide Streamlit native UI (Stop, Deploy, hamburger) for end users
- Manager view toggle gated by role
- Update `departure_date` per case to ~1 week from rollout (now handled by dynamic tokens automatically)
