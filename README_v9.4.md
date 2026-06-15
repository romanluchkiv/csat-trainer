# CSAT Trainer — v9.4 (patch on top of v9.3)

## What's NEW in v9.4

5 targeted fixes based on Roman's testing of v9.3.

### 1. Case 2 (Egypt safety) opening rewritten with accident + 7h delay
- Old opening described reckless driving but didn't include a clear "service not delivered" event — Ops would sometimes hesitate on full refund grounds.
- New opening adds: highway accident around 2am, ~7-hour roadside delay, damaged WWII Ruksac from the impact, terrified customer arriving exhausted hours late.
- Now cleanly qualifies for full refund + luggage compensation under safety policy.

### 2. Ops/IT no longer cite ToU clause numbers
- Real 12Go SOP: Ops/IT respond in plain language. Citing the correct ToU clause is the **agent's** responsibility.
- v9.3 had Ops saying "Per clause 6, refund authorized" — that was leaking the policy to the agent.
- v9.4 example responses updated: "Refund authorized given safety failure" instead of "Per clause 6, refund authorized".
- Explicit ban added to both OPS_TEAM_SYSTEM_PROMPT and IT_TEAM_SYSTEM_PROMPT.
- Coach still verifies the agent referenced the correct clause in public/internal — but Ops no longer gives the answer away.

### 3. Customers no longer demand "speak to a manager / supervisor"
- v9.3 had a few openings where the customer wrote "Put me through to a supervisor immediately" — but in real 12Go, manager escalation is an SOP path that some agents use and others don't. The simulator focuses on **this agent's own resolution**, not the transfer flow.
- CLIENT_SYSTEM_PROMPT now explicitly prohibits "transfer me to a manager" / "I want to speak to your supervisor" type demands. Customers can still threaten chargeback, reviews, consumer protection — but not manager transfer.
- Coach rule (G) added: if agent **promises** "I'll escalate to my manager" for a clause-4 wrong-dropoff case (where no real manager queue exists), that's a broken promise. Real 12Go SOP for clause 4 is to hold the position firmly.

### 4. Booking ID prefix duplication fixed
- v9.3 showed "BID: BID 6367210" — double prefix because JSON had "BID 6367210" and the UI added "BID:".
- v9.4 stores just the digits ("6367210") in JSON and renders "Booking ID: 6367210" in the UI.
- Enrichment script now generates booking IDs without prefix.
- Re-running the enrichment script will strip "BID " from any existing JSON values.

### 5. Final summary case labels simplified
- v9.3 showed "Case 1: Case 2 — 5/5" (because case_title had its own numbering) — confusing.
- v9.4 shows just "Case 1 — 5/5" in the final breakdown. Title from JSON is no longer in the label.

---

## Installation

### Step 1 — Stop Streamlit
Ctrl+C in the terminal where it's running.

### Step 2 — Replace 3 files + add 1 new file
Inside `~/Desktop/csat_trainer/`:
- Replace `trainer.py` with the v9.4 version
- Replace `prompts.py` with the v9.4 version
- Replace `enrich_v9_metadata.py` with the v9.4 version
- Add `patch_v9_4_openings.py` (new — used once to rewrite Case 2 opening)

### Step 3 — Run the one-shot opening patch
This rewrites Case 2 opening and strips manager demands from all 4 case openings:

```bash
cd ~/Desktop/csat_trainer
source venv/bin/activate
python patch_v9_4_openings.py
```

You should see output like:
```
v9.4 — Case 2 opening rewrite + manager demand cleanup

  case_636721.json (Case 2): opening rewritten with accident + 7h delay scenario
  case_973250.json: manager/supervisor demands removed from opening
  case_748911.json: no manager/supervisor demands in opening (already clean)
  case_784988.json: no manager/supervisor demands in opening (already clean)

Done.
```

### Step 4 — Re-run enrichment to strip BID prefix from existing JSON
```bash
python enrich_v9_metadata.py
```

You should see lines like:
```
--- case_636721.json ---
  Applied fixes: booking_id stripped to 6367210
  Saved.
```

(if it says "already present" for everything — the BID prefix was already stripped, OK.)

### Step 5 — Launch
```bash
streamlit run trainer.py
```

### Step 6 — Verify
- Case 2 opening message starts with "Hello. I want to file a serious complaint... We were involved in an accident on the highway..."
- Booking Info sidebar shows **"Booking ID: 6367210"** (no double BID)
- Ops replies do NOT mention "clause 6" or "per clause N" anywhere
- IT replies do NOT mention clause numbers either
- If you do a wrong-dropoff case (Case 3) and promise the customer manager escalation, Coach should flag it as a broken promise
- Final summary shows "Case 1 — 5/5", not "Case 1: Case 2 — 5/5"

---

## Files in v9.4

| File | Changed in v9.4? |
|---|---|
| `trainer.py` | ✅ Patched (case label fix, Booking ID label) |
| `prompts.py` | ✅ Patched (Ops/IT no clauses, Coach rule G, client no-manager) |
| `enrich_v9_metadata.py` | ✅ Patched (BID strip + no-prefix generation) |
| `patch_v9_4_openings.py` | ✅ NEW (one-shot Case 2 opening rewrite + manager-demand cleanup) |
| `rules.md` | — unchanged from v9.3 |
| `agent_roster.csv` | — unchanged |
| `12go_logo.jpg` | — unchanged |

---

## What's still NOT done (FINAL release backlog)

Nothing from your test discovery today is left in v9.4. All 5 issues addressed.

For the bigger FINAL release (multi-user deploy with persistent storage, manager dashboard, etc.) — that's the next phase after you ship the manager pilot.
