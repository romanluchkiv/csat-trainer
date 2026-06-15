# CSAT Trainer — v9.3 (Manager Pilot Edition)

## What's NEW in v9.3

This version transforms the simulator from a **local tool** into a **manager pilot assessment**.

### New flow

```
1. Welcome screen — enter your work email
   ↓ (email checked against agent_roster.csv whitelist)
2. Rules screen — read the rules, click "Start Case 1"
   ↓
3. Case 1 — full simulation (reply, escalate, get Ops/IT response, etc.)
   ↓ (case ends silently — NO CSAT shown)
4. "Case 1 complete. Continue to Case 2" → Case 2 → Case 3 → Case 4
   ↓
5. Final results screen:
   - Aggregate score on 0-100 scale
   - Recommendation tier (Strong / Good / Training recommended / Urgent)
   - Per-case breakdown (collapsed accordions with verdict + strengths + gaps + emotional ack)
```

### What changed under the hood

- **Phase machine** (`auth → rules → in_case → between_cases → complete`) replaces the old "pick a case from the dropdown" flow.
- **Email whitelist authentication** — only emails listed in `agent_roster.csv` may log in.
- **Sequential cases** — Case 1 → 2 → 3 → 4 in fixed order. No case picker.
- **CSAT is hidden between cases.** Per-case verdicts are generated and stored silently, then revealed all together on the final screen. This prevents Coach feedback from leaking into later cases.
- **Aggregate score on 0-100 scale**: each case 1-5 maps to 20-100, average across all completed cases.
- **Recommendation tiers** based on aggregate score:
  - 80-100 → 🏆 Strong (share approach with team)
  - 60-79 → 👍 Good (review gaps with manager)
  - 40-59 → 📚 Training recommended (1h with manager)
  - 0-39 → 🚨 Urgent 1:1 needed
- **Streamlit native UI hidden** — Stop, Deploy, hamburger menu, and "Made with Streamlit" footer are hidden from end users via CSS.
- **Manager view toggle removed** in this pilot version. Everyone sees the agent-level view (verdict + emotional ack + strengths + gaps). The detailed manager view (per-turn breakdown + promises tracker) will return in the next version, gated by role.
- **Sidebar simplified**: just the agent's name and progress bar (Case X of 4). No buttons to skip, restart, or pick.
- **Rules text** loaded from `rules.md` so you can edit it without touching code.

### v9.1 and v9.2 fixes inherited

All previous fixes carry over: dynamic departure dates, IT/Ops split, "Dear CS" salutation, real refund policy (clause 4 = Grab fee only + promo), urgency-aware Wait button, customer fact consistency, attachment markers in follow-ups, structured Judge tool, yellow internal notes with dark text, larger fonts, real 12Go logo, etc.

---

## What is NOT included yet (FINAL release scope)

These come in the next deployment iteration after the manager pilot returns feedback:

- 45-minute countdown timer
- Persistent storage (Google Sheet integration) — currently logs go to local `logs/sessions.csv`, which is **ephemeral on Streamlit Cloud**
- Manager dashboard
- Resume-if-closed-browser logic
- Stylistic AI-detection (post-session check)
- Manager view toggle gated by role
- Agent rollout (broader audience)

---

## Installation (local first)

### Step 1 — Stop your current Streamlit
Ctrl+C in the terminal where it's running.

### Step 2 — Replace files
Inside `~/Desktop/csat_trainer/`:

- Replace `trainer.py` with the v9.3 version
- Add `rules.md` (new file — drop directly into the folder)
- `prompts.py`, `enrich_v9_metadata.py`, `agent_roster.csv`, `12go_logo.jpg` stay as they are

### Step 3 — Update the agent roster (whitelist)
Edit `agent_roster.csv` and add every manager you want to give access to. Format per line:

```
email,Full Name
```

Lines starting with `#` are ignored. Example:

```
roman.luchkiv@12go.asia,Roman Luchkiv
volodymyr.k@12go.asia,Volodymyr Krokhmalnyi
manager1@12go.asia,Manager One
manager2@12go.asia,Manager Two
```

**Only these emails can log in.** Anyone else gets "That email isn't on the access list."

### Step 4 — Customize the rules text (optional)
Open `rules.md` and edit. This is what every user sees on the welcome screen after they enter their email. Markdown supported.

### Step 5 — Launch
```bash
cd ~/Desktop/csat_trainer
source venv/bin/activate
streamlit run trainer.py
```

### Step 6 — Walk through it yourself first
- Enter your email
- Read the rules
- Run through Case 1 → Case 2 → Case 3 → Case 4
- Confirm you only see the aggregate score at the end (not between cases)

---

## Deploying to Streamlit Cloud (for the 5-manager pilot)

This is the part where the pilot becomes **accessible from anywhere**.

### Step 1 — Create a GitHub repo
1. Sign in to github.com
2. Click **+** → New repository
3. Name it `csat-trainer` (private!)
4. Don't initialize with README — we'll push from local

### Step 2 — Push your local code
In `~/Desktop/csat_trainer/`:

```bash
git init
git add .
git commit -m "v9.3 manager pilot"
git remote add origin https://github.com/YOUR_USERNAME/csat-trainer.git
git branch -M main
git push -u origin main
```

⚠️ **Before pushing**, double-check that `.env` is NOT committed (it should be in `.gitignore`). Your API key must NEVER be in the repo.

### Step 3 — Deploy on Streamlit Cloud
1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **New app**
4. Choose your `csat-trainer` repo, branch `main`, main file `trainer.py`
5. Click **Advanced settings**
6. Under **Secrets**, paste:
   ```
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
7. Click **Deploy**

After ~30 seconds you'll get a URL like `https://csat-trainer-xyz.streamlit.app`. That's your manager pilot link.

### Step 4 — Share with managers
Send each manager:

> Hey [name], here's the CSAT training simulator we're piloting: `https://csat-trainer-xyz.streamlit.app`
>
> Use your 12Go email to log in (I've added you to the whitelist). You'll go through 4 cases, ~40 minutes total. Reply in your own words, no AI tools please. Results are shown at the end.
>
> Send any feedback back to me. Thanks!

### Step 5 — Pull logs after they're done
Logs go to `logs/sessions.csv` **on the Streamlit Cloud server**, which is **ephemeral**. To pull them:

- Streamlit Cloud allows you to download files from the app's session if you implement a small download helper, OR
- Use Streamlit Cloud's **"App settings → Reboot app"** to keep the session alive for short pilots
- For a 5-person pilot done in 1-2 days, manual sharing of results (managers screenshot their final score and send you in Slack) is the cheapest path

**Persistent storage to Google Sheet is the next iteration**, not this one.

---

## Files in v9.3

| File | New / Changed |
|---|---|
| `trainer.py` | ✅ Rewritten — phase machine, auth, sequential cases, aggregate score |
| `rules.md` | ✅ NEW — onboarding text (edit freely) |
| `prompts.py` | — unchanged (from v9.2) |
| `enrich_v9_metadata.py` | — unchanged (from v9.2) |
| `agent_roster.csv` | — unchanged structure, but you'll add manager emails |
| `12go_logo.jpg` | — unchanged |

---

## What to test before sending to managers

1. **Email whitelist works** — try a fake email, should get rejected
2. **Sequential flow** — finish Case 1, see "Case 1 complete. Continue to Case 2" (no CSAT)
3. **Final summary appears** — after Case 4, you see aggregate score + per-case accordions
4. **Per-case scores match what you'd expect** — bad agent gets low aggregate, good agent gets high
5. **No "Pick a case" dropdown anywhere** — flow is fully linear
6. **No Streamlit Deploy/Stop buttons visible** in the top-right corner
7. **Sidebar shows progress bar** "Case X of 4"

If all six pass — you can deploy.
