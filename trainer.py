"""
CSAT Trainer — v9.3 (Manager Pilot Edition)

Run with:
    streamlit run trainer.py

What's new in v9.3:
- Manager pilot flow: email auth → rules → 4 cases sequentially → final summary.
- No case picker — cases run in fixed order (case_*.json sorted).
- CSAT per case is HIDDEN between cases. All verdicts shown only on the FINAL screen.
- Aggregate score on a 0-100 scale + recommendation for next steps.
- Streamlit native UI (Stop / Deploy / hamburger) hidden from end users.
- Manager view toggle removed (this version shows the agent-level verdict only).

Inherits all v9.1 / v9.2 fixes: dynamic dates, IT/Ops split, structured Judge,
"Dear CS" salutation, real refund policy, urgency-aware Wait button, fact
consistency in customer LLM, attachment markers in follow-ups, etc.
"""
import os
import json
import csv
import datetime as dt
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic

from prompts import (
    CLIENT_SYSTEM_PROMPT,
    JUDGE_TOOL_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
    OPS_TEAM_SYSTEM_PROMPT,
    IT_TEAM_SYSTEM_PROMPT,
    REFUND_POLICY_RULES,
    detect_internal_note_addressee,
)


load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

BASE = Path(__file__).parent
CASES_DIR = BASE / 'cases'
LOGS_DIR = BASE / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / 'sessions.csv'

# Whitelist of emails — only people in this file may log in. Format per line:
#   email,Full Name
# Lines starting with # are ignored.
ROSTER_FILE = BASE / 'agent_roster.csv'

# Rules / intro text shown on the welcome screen. Edit freely (markdown).
RULES_FILE = BASE / 'rules.md'

BRAND_GREEN = '#5DBE3F'
LOGO_PATH = BASE / '12go_logo.jpg'


# ============================================================================
# Helpers
# ============================================================================

def get_client():
    if 'anthropic_client' not in st.session_state:
        st.session_state.anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return st.session_state.anthropic_client


def resolve_date_tokens(value):
    """v9.2: Resolve dynamic date tokens in case JSON values."""
    if not isinstance(value, str) or '{{' not in value:
        return value

    import re
    now = dt.datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def fmt(d):
        return d.strftime('%d-%b-%Y %H:%M')

    def replace_token(match):
        tok = match.group(1)
        if tok == 'TODAY':
            return fmt(today)
        if tok == 'TOMORROW':
            return fmt(today + dt.timedelta(days=1))
        if tok == 'YESTERDAY':
            return fmt(today - dt.timedelta(days=1))
        if tok == 'NOW':
            return fmt(now)
        m = re.match(r'^TODAY_PLUS_DAYS_(\d+)$', tok)
        if m:
            return fmt(today + dt.timedelta(days=int(m.group(1))))
        m = re.match(r'^TODAY_MINUS_DAYS_(\d+)$', tok)
        if m:
            return fmt(today - dt.timedelta(days=int(m.group(1))))
        m = re.match(r'^TOMORROW_PLUS_HOURS_(\d+)$', tok)
        if m:
            tomorrow = today + dt.timedelta(days=1)
            return fmt(tomorrow.replace(hour=int(m.group(1))))
        return match.group(0)

    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', replace_token, value)


def resolve_case_tokens(case_data):
    bf = case_data.get('booking_facts', {})
    if 'departure_date' in bf:
        bf['departure_date'] = resolve_date_tokens(bf['departure_date'])
    # Compute arrival_date from departure + duration_hours, if both present
    if 'departure_date' in bf and 'duration_hours' in bf:
        try:
            dep_dt = dt.datetime.strptime(bf['departure_date'], '%d-%b-%Y %H:%M')
            duration = float(bf['duration_hours'])
            arr_dt = dep_dt + dt.timedelta(hours=duration)
            bf['arrival_date'] = arr_dt.strftime('%d-%b-%y %H:%M')
            # Reformat departure to 2-digit year too, to match Zendesk style
            bf['departure_date'] = dep_dt.strftime('%d-%b-%y %H:%M')
        except (ValueError, TypeError):
            pass
    return case_data


def load_cases():
    """Load and sort cases by filename (case_*.json)."""
    cases = []
    for f in sorted(CASES_DIR.glob('case_*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            data = resolve_case_tokens(data)
            cases.append({'file': f.name, 'data': data})
        except Exception as e:
            st.warning(f"Could not load {f.name}: {e}")
    return cases


def load_roster():
    """Return dict: email → name (lowercase emails). Whitelist for login."""
    out = {}
    if not ROSTER_FILE.exists():
        return out
    with ROSTER_FILE.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',', 1)
            if len(parts) == 2:
                email, name = parts[0].strip().lower(), parts[1].strip()
                out[email] = name
    return out


def load_rules_text():
    if RULES_FILE.exists():
        return RULES_FILE.read_text(encoding='utf-8')
    return (
        "## CSAT Training Simulator\n\n"
        "You will go through 4 customer support cases in sequence.\n\n"
        "**Rules:**\n"
        "- Treat each case as if it were a real Zendesk ticket.\n"
        "- Reply in your own words. Macros from Zendesk are fine; AI tools are not.\n"
        "- You'll see your full results only at the end, not between cases.\n\n"
        "Click **Start** to begin Case 1."
    )


def aggregate_score(verdicts):
    """Compute 0-100 score from list of per-case verdicts (each has csat_score 1-5)."""
    if not verdicts:
        return 0
    total = sum((v.get('csat_score', 0) / 5) * 100 for v in verdicts)
    return round(total / len(verdicts))


def recommendation_for_score(score):
    """Return (tier_label, message)."""
    if score >= 80:
        return ('🏆 Strong', "Excellent work. Consider sharing your approach with the team in your next 1:1.")
    if score >= 60:
        return ('👍 Good', "Solid foundation with room to grow. Review the case gaps below and discuss with your manager.")
    if score >= 40:
        return ('📚 Training recommended', "Contact your manager to schedule a 1-hour training session focused on the gaps below.")
    return ('🚨 Urgent training needed', "Contact your manager today to schedule a 1:1. The gaps below indicate critical patterns to address.")


def init_phase():
    """Initialise the phase machine on first load."""
    if 'phase' not in st.session_state:
        st.session_state.phase = 'auth'
        st.session_state.agent_email = None
        st.session_state.agent_name = None
        st.session_state.case_queue = []
        st.session_state.current_case_index = 0
        st.session_state.all_verdicts = []  # one verdict per completed case


def init_case_state(case_data):
    """Reset per-case state and seed with opening message."""
    customer_name = case_data.get('customer_name', 'Customer')
    st.session_state.current_case = case_data
    st.session_state.session_started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    st.session_state.conversation = [
        {'role': 'customer', 'content': case_data['opening_message'], 'name': customer_name}
    ]
    st.session_state.turn_count = 0
    st.session_state.internal_turn_count = 0
    st.session_state.case_complete = False
    st.session_state.feedback_log = []
    st.session_state.reply_mode = 'public'


def advance_to_next_case(verdict):
    """Store the verdict, increment index, decide next phase."""
    st.session_state.all_verdicts.append(verdict)
    st.session_state.current_case_index += 1
    if st.session_state.current_case_index >= len(st.session_state.case_queue):
        st.session_state.phase = 'complete'
    else:
        st.session_state.phase = 'between_cases'
    # Clear per-case state
    for k in ('current_case', 'conversation', 'turn_count', 'internal_turn_count',
              'case_complete', 'feedback_log', 'reply_mode', 'session_started_at'):
        if k in st.session_state:
            del st.session_state[k]


# ============================================================================
# LLM calls (unchanged from v9.2)
# ============================================================================

def get_customer_reply(client, case_data, conversation):
    profile = case_data['customer_profile']
    system = CLIENT_SYSTEM_PROMPT.format(
        customer_name=case_data.get('customer_name', 'Customer'),
        situation=profile['situation'],
        emotional_state=profile['emotional_state'],
        personality_notes=profile['personality_notes'],
        case_language=case_data['case_language'],
    )
    api_messages = []
    for turn in conversation[1:]:
        role = turn['role']
        if role == 'customer':
            api_messages.append({'role': 'assistant', 'content': turn['content']})
        elif role == 'agent_public':
            api_messages.append({'role': 'user', 'content': turn['content']})
    if not api_messages or api_messages[0]['role'] != 'assistant':
        api_messages.insert(0, {'role': 'assistant', 'content': conversation[0]['content']})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=system,
        messages=api_messages,
    )
    return response.content[0].text.strip()


def get_ops_reply(client, case_data, agent_note_text, previous_internal_history):
    bf = case_data.get('booking_facts', {})
    system = OPS_TEAM_SYSTEM_PROMPT.format(
        booking_id=case_data.get('booking_id', 'N/A'),
        route=bf.get('route', 'Not specified'),
        departure_date=bf.get('departure_date', 'Not specified'),
        operator_name=bf.get('operator_name', 'Not specified'),
        confirmation_type=case_data.get('confirmation_type', 'instant'),
        booking_status=bf.get('booking_status', 'Not specified'),
        pickup_address=case_data.get('pickup_address', 'Not specified'),
        dropoff_address=case_data.get('dropoff_address', 'Not specified'),
        refund_policy=bf.get('refund_policy', 'Not specified'),
        customer_country=bf.get('customer_country', 'Not specified'),
        ops_context=case_data.get('ops_team_context', {}).get('typical_outcome', 'Standard ops handling.'),
        policy_rules=REFUND_POLICY_RULES,
    )
    messages = []
    for turn in previous_internal_history:
        if turn['role'] == 'agent_internal':
            messages.append({'role': 'user', 'content': turn['content']})
        elif turn['role'] in ('ops', 'it'):
            messages.append({'role': 'assistant', 'content': turn['content']})
    messages.append({'role': 'user', 'content': agent_note_text})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()


def get_it_reply(client, case_data, agent_note_text, previous_internal_history):
    system = IT_TEAM_SYSTEM_PROMPT.format(
        booking_id=case_data.get('booking_id', 'N/A'),
        customer_country=case_data.get('booking_facts', {}).get('customer_country', 'Not specified'),
        it_context=case_data.get('it_context', 'Standard technical investigation.'),
    )
    messages = []
    for turn in previous_internal_history:
        if turn['role'] == 'agent_internal':
            messages.append({'role': 'user', 'content': turn['content']})
        elif turn['role'] in ('ops', 'it'):
            messages.append({'role': 'assistant', 'content': turn['content']})
    messages.append({'role': 'user', 'content': agent_note_text})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()


def get_final_verdict_structured(client, case_data, conversation):
    transcript_parts = []
    turn_idx = 0
    for turn in conversation:
        role = turn['role']
        if role == 'customer':
            turn_idx += 1
            transcript_parts.append(f"[CUSTOMER, msg {turn_idx}]: {turn['content']}")
        elif role == 'agent_public':
            transcript_parts.append(f"[AGENT PUBLIC]: {turn['content']}")
        elif role == 'agent_internal':
            transcript_parts.append(f"[AGENT INTERNAL NOTE]: {turn['content']}")
        elif role == 'ops':
            transcript_parts.append(f"[OPS TEAM REPLY]: {turn['content']}")
        elif role == 'it':
            transcript_parts.append(f"[IT TEAM REPLY]: {turn['content']}")
    transcript = '\n\n'.join(transcript_parts)

    tou_clauses = case_data.get('applicable_tou_clauses', [])
    tou_str = str(tou_clauses) if tou_clauses else '[]'
    clause_descriptions_map = {
        1: "Clause 1: Non-refundable by default unless exception applies.",
        2: "Clause 2: Operator cancellation → 100% refund.",
        3: "Clause 3: 12Go technical error verified by IT → exception refund possible.",
        4: "Clause 4: Wrong dropoff / door-to-door failure → refund EXTRA COSTS ONLY (taxi/Grab) at operator's expense; original booking NOT refunded; promo code may be added as goodwill.",
        5: "Clause 5: No-show by customer → no refund.",
        6: "Clause 6: Safety issue or service not delivered → 100% refund + escalation.",
        7: "Clause 7: Schedule change >2h → 100% refund.",
        8: "Clause 8: Unconfirmed booking (manual confirmation, no operator response in time) → 100% refund; CS to process manually (not auto-triggered).",
        9: "Clause 9: Customer-side document/visa issues → no refund.",
    }
    tou_descriptions = '\n'.join(clause_descriptions_map.get(c, '') for c in tou_clauses) if tou_clauses else '(No specific clauses apply.)'

    system = JUDGE_SYSTEM_PROMPT.format(
        case_title=case_data['case_title'],
        situation=case_data['customer_profile']['situation'],
        what_would_earn_5=case_data['csat_drivers']['what_would_earn_5'],
        what_would_earn_1=case_data['csat_drivers']['what_would_earn_1'],
        applicable_tou_clauses=tou_str,
        tou_descriptions=tou_descriptions,
        red_flag_phrases='\n'.join(f'- {p}' for p in case_data.get('red_flag_phrases', [])) or '(none)',
        internal_process_gaps='\n'.join(f'- {p}' for p in case_data.get('internal_process_gaps', [])) or '(none)',
    )

    user_msg = f"FULL CONVERSATION TRANSCRIPT:\n\n{transcript}\n\nUse the submit_csat_verdict tool to record your verdict."

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        system=system,
        messages=[{'role': 'user', 'content': user_msg}],
        tools=[JUDGE_TOOL_SCHEMA],
        tool_choice={'type': 'tool', 'name': 'submit_csat_verdict'},
    )

    for block in response.content:
        if block.type == 'tool_use' and block.name == 'submit_csat_verdict':
            return block.input

    return {
        'csat_score': 0,
        'customer_comment': '(Verdict could not be generated — please retry.)',
        'verdict_for_agent': 'Tool call did not return structured output.',
        'key_strengths': [],
        'key_gaps': ['Session verdict could not be generated due to a technical issue.'],
        'emotional_acknowledgment': {'passed': False, 'explanation': 'Unable to evaluate.'},
        'tou_clauses_referenced': [],
        'phrase_repetition_flagged': False,
        'red_flag_phrases_used': [],
        'internal_process_followed': 'not_applicable',
        'resolution_status': 'unresolved',
        'promises_kept': [],
        'promises_broken': [],
        'per_turn_review': [],
    }


def _ea_passed(verdict):
    """Safely extract emotional_acknowledgment.passed even if LLM returns a string."""
    ea = verdict.get('emotional_acknowledgment', {})
    if isinstance(ea, dict):
        return ea.get('passed', False)
    return False


def log_session(case_data, agent_email, agent_name, conversation, verdict, feedback_log, started_at, case_index):
    is_new = not LOG_FILE.exists()
    with LOG_FILE.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow([
                'timestamp', 'agent_email', 'agent_name', 'case_index',
                'case_title', 'source_ticket_id',
                'csat_score', 'resolution_status', 'emotional_ack_passed',
                'turn_count', 'verdict_summary',
                'conversation_json', 'feedback_json', 'full_verdict_json',
            ])
        writer.writerow([
            started_at, agent_email, agent_name, case_index,
            case_data.get('case_title'),
            case_data.get('source_ticket_id'),
            verdict.get('csat_score'),
            verdict.get('resolution_status'),
            _ea_passed(verdict),
            len([t for t in conversation if t['role'].startswith('agent')]),
            verdict.get('verdict_for_agent', ''),
            json.dumps(conversation, ensure_ascii=False),
            json.dumps(feedback_log, ensure_ascii=False),
            json.dumps(verdict, ensure_ascii=False),
        ])


# ============================================================================
# UI
# ============================================================================

st.set_page_config(page_title='12Go CSAT Trainer', layout='wide')

# Hide Streamlit native UI for end users + increase base font
st.markdown(
    '''
    <style>
        /* Hide Streamlit branded UI */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        .stDeployButton { display: none !important; }
        [data-testid="stToolbar"] { visibility: hidden; }
        [data-testid="stStatusWidget"] { visibility: hidden; }
        header { visibility: hidden; }

        /* Font sizes */
        html, body, [class*="css"] { font-size: 17px !important; }
        .stMarkdown, .stMarkdown p, .stMarkdown li { font-size: 16px !important; }
        .stCaption, .stMarkdown small, [data-testid="stCaptionContainer"] { font-size: 14px !important; }
        h1 { font-size: 32px !important; }
        h2 { font-size: 26px !important; }
        h3 { font-size: 22px !important; }
        h4 { font-size: 19px !important; }
        [data-testid="stSidebar"] .stMarkdown { font-size: 16px !important; }
        .stChatMessage p { font-size: 16px !important; }
    </style>
    ''',
    unsafe_allow_html=True,
)

# Header — logo + title (always visible)
header_cols = st.columns([1, 5])
with header_cols[0]:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=80)
    else:
        st.markdown(
            f'<div style="background:{BRAND_GREEN};color:white;font-weight:700;'
            f'font-size:22px;padding:8px 14px;border-radius:8px;display:inline-block;">'
            f'12Go</div>',
            unsafe_allow_html=True,
        )
with header_cols[1]:
    st.markdown('### CSAT Trainer')
    st.caption('Practice real customer scenarios. Get feedback. Improve.')

if not ANTHROPIC_API_KEY:
    st.error('ANTHROPIC_API_KEY missing in .env')
    st.stop()

init_phase()
phase = st.session_state.phase


# ----- PHASE: auth -----
if phase == 'auth':
    st.markdown('### Welcome')
    st.markdown('Please enter your 12Go work email to begin the training simulator.')
    with st.form('auth_form'):
        email_input = st.text_input('Email', placeholder='you@12go.asia')
        submitted = st.form_submit_button('Continue', type='primary')

    if submitted:
        email_clean = email_input.strip().lower()
        roster = load_roster()
        if not roster:
            st.error('No agents configured (agent_roster.csv is empty or missing).')
        elif email_clean not in roster:
            st.error("That email isn't on the access list. Please contact your manager.")
        else:
            st.session_state.agent_email = email_clean
            st.session_state.agent_name = roster[email_clean]
            cases = load_cases()
            if not cases:
                st.error('No cases found in /cases — contact your administrator.')
                st.stop()
            st.session_state.case_queue = cases
            st.session_state.current_case_index = 0
            st.session_state.all_verdicts = []
            st.session_state.phase = 'rules'
            st.rerun()
    st.stop()


# ----- PHASE: rules -----
if phase == 'rules':
    st.markdown(f'### Hello, {st.session_state.agent_name}')
    st.markdown(load_rules_text())
    if st.button('Start Case 1', type='primary'):
        case_data = st.session_state.case_queue[0]['data']
        init_case_state(case_data)
        st.session_state.phase = 'in_case'
        st.rerun()
    st.stop()


# ----- PHASE: between_cases -----
if phase == 'between_cases':
    next_index = st.session_state.current_case_index  # already incremented
    completed = next_index
    total = len(st.session_state.case_queue)
    st.markdown(f'### Case {completed} of {total} complete ✅')
    st.markdown(
        'Your detailed results will be shown after you complete all cases. '
        'Take a moment if you need it, then continue.'
    )
    st.progress(completed / total)
    if st.button(f'Continue to Case {next_index + 1}', type='primary'):
        case_data = st.session_state.case_queue[next_index]['data']
        init_case_state(case_data)
        st.session_state.phase = 'in_case'
        st.rerun()
    st.stop()


# ----- PHASE: complete (final summary) -----
if phase == 'complete':
    verdicts = st.session_state.all_verdicts
    total_score = aggregate_score(verdicts)
    tier_label, tier_msg = recommendation_for_score(total_score)

    st.divider()
    st.markdown('## 🎯 Your training results')
    st.markdown(f'**{st.session_state.agent_name}** — {len(verdicts)} cases completed')

    # Big aggregate score
    score_col, tier_col = st.columns([1, 2])
    with score_col:
        if total_score >= 80:
            st.success(f'### Overall: {total_score} / 100')
        elif total_score >= 60:
            st.warning(f'### Overall: {total_score} / 100')
        else:
            st.error(f'### Overall: {total_score} / 100')
    with tier_col:
        st.markdown(f'### {tier_label}')
        st.markdown(tier_msg)

    st.divider()

    # Per-case breakdown
    st.markdown('### Per-case breakdown')
    for i, v in enumerate(verdicts):
        score = v.get('csat_score', 0)
        score_label = f'{score} / 5'
        ea_raw = v.get('emotional_acknowledgment', {})
        if not isinstance(ea_raw, dict):
            ea_raw = {'passed': False, 'explanation': str(ea_raw)}
        ea_passed = ea_raw.get('passed', False)
        ea_explanation = ea_raw.get('explanation', '')
        ea_icon = '✅' if ea_passed else '❌'

        with st.expander(f'Case {i + 1}  —  {score_label}  {ea_icon}', expanded=False):
            res = v.get('resolution_status', 'unknown')
            res_label_map = {
                'resolved': '✅ Resolved',
                'partially_resolved': '⚠️ Partially resolved',
                'unresolved': '❌ Unresolved',
            }
            st.markdown(f"**Status:** {res_label_map.get(res, res)}")

            cc = v.get('customer_comment', '')
            if cc:
                st.markdown(f"**Customer comment:** _{cc}_")

            st.markdown('**Coach verdict**')
            st.markdown(v.get('verdict_for_agent', ''))

            if ea_passed:
                st.success(f"✅ **Emotional acknowledgment — strong.** {ea_explanation}")
            else:
                st.error(f"❌ **Emotional acknowledgment — missing.** {ea_explanation}")

            sg_col1, sg_col2 = st.columns(2)
            with sg_col1:
                st.markdown('**✅ Strengths**')
                for s in v.get('key_strengths', []) or ['(none noted)']:
                    st.markdown(f'- {s}')
            with sg_col2:
                st.markdown('**🔧 Gaps to work on**')
                for g in v.get('key_gaps', []) or ['(none)']:
                    st.markdown(f'- {g}')

    st.divider()
    st.markdown(
        '_Thank you for completing the simulator. Please share any feedback with your manager._'
    )
    st.stop()


# ----- PHASE: in_case -----
if phase != 'in_case' or 'current_case' not in st.session_state:
    st.error('Unexpected state. Please refresh.')
    st.stop()

case = st.session_state.current_case
case_idx = st.session_state.current_case_index  # 0-based, current
total_cases = len(st.session_state.case_queue)

# Sidebar — progress only (no case picker, no restart)
with st.sidebar:
    st.markdown(f'**{st.session_state.agent_name}**')
    st.caption(st.session_state.agent_email)
    st.divider()
    st.markdown(f'### Case {case_idx + 1} of {total_cases}')
    st.progress(case_idx / total_cases)
    st.caption('Your results will be shown after the final case.')

# Two-column layout
col_main, col_info = st.columns([3, 1])

# Booking info
with col_info:
    st.markdown('#### Booking information')
    bf = case.get('booking_facts', {})
    st.markdown(f"**Booking ID:** {case.get('booking_id', 'N/A')}")
    st.markdown(f"**Route:** {bf.get('route', 'N/A')}")
    if bf.get('arrival_date'):
        st.markdown(f"**Departure:** {bf.get('departure_date', 'N/A')}")
        st.markdown(f"**Arrival:** {bf.get('arrival_date')}")
    else:
        st.markdown(f"**Departure:** {bf.get('departure_date', 'N/A')}")
    if bf.get('total_price'):
        st.markdown(f"**Total price:** {bf.get('total_price')}")
    st.markdown(f"**Operator:** {bf.get('operator_name', 'N/A')}")
    st.markdown(f"**Confirmation:** {case.get('confirmation_type', 'instant')}")
    st.markdown(f"**Status:** {bf.get('booking_status', 'N/A')}")
    st.markdown(f"**Pickup:** {case.get('pickup_address', 'N/A')}")
    st.markdown(f"**Dropoff:** {case.get('dropoff_address', 'N/A')}")
    st.markdown(f"**Refund policy:** {bf.get('refund_policy', 'N/A')}")
    if bf.get('customer_country'):
        st.markdown(f"**Customer country:** {bf['customer_country']}")

# Main: conversation + reply
with col_main:
    customer_name = case.get('customer_name', 'Customer')

    for turn in st.session_state.conversation:
        role = turn['role']
        if role == 'customer':
            with st.chat_message('user', avatar='👤'):
                st.markdown(f"**{customer_name}**")
                content = turn['content']
                attachment_marker = '[Attachments:'
                if attachment_marker in content:
                    main_text, _, attach_part = content.partition(attachment_marker)
                    if main_text.strip():
                        st.markdown(main_text.strip())
                    attach_desc = attach_part.split(']', 1)[0].strip()
                    st.info(
                        f"📎 Attachment(s) received — simulation placeholder\n\n"
                        f"In a real Zendesk ticket, image/video files would appear here.\n\n"
                        f"Contents: {attach_desc}"
                    )
                else:
                    st.markdown(content)
        elif role == 'agent_public':
            with st.chat_message('assistant', avatar='🧑\u200d💼'):
                st.markdown(turn['content'])
        elif role == 'agent_internal':
            addressee = turn.get('addressee', 'ops').upper()
            st.markdown(
                f'<div style="background-color:#FFF8DC;color:#1a1a1a;border-left:4px solid #DAA520;'
                f'padding:10px 14px;border-radius:4px;margin:8px 0;">'
                f'<strong>📝 Internal note to {addressee} team</strong><br><br>'
                f'{turn["content"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif role == 'ops':
            st.markdown(
                f'<div style="background-color:#FFF8DC;color:#1a1a1a;border-left:4px solid #B8860B;'
                f'padding:10px 14px;border-radius:4px;margin:8px 0;">'
                f'<strong>📋 Ops team reply — internal</strong><br><br>'
                f'{turn["content"]}'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif role == 'it':
            st.markdown(
                f'<div style="background-color:#FFF8DC;color:#1a1a1a;border-left:4px solid #4682B4;'
                f'padding:10px 14px;border-radius:4px;margin:8px 0;">'
                f'<strong>🛠️ IT team reply — internal</strong><br><br>'
                f'{turn["content"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Case-complete handoff (no verdict shown — saved silently)
    if st.session_state.case_complete:
        st.divider()
        st.markdown(f'### Case {case_idx + 1} complete')
        next_label = (
            f'Continue to Case {case_idx + 2}'
            if case_idx + 1 < total_cases
            else 'See your final results'
        )
        if st.button(next_label, type='primary'):
            advance_to_next_case(st.session_state.pending_verdict)
            del st.session_state['pending_verdict']
            st.rerun()
        st.stop()

    # Input section
    max_turns = case.get('max_turns', 5)
    max_internal_turns = case.get('max_internal_turns', 3)
    turns_used = st.session_state.turn_count
    internal_used = st.session_state.internal_turn_count

    st.divider()

    mode = st.radio(
        'Reply type',
        options=['public', 'internal'],
        format_func=lambda m: '📧 Public reply to customer' if m == 'public' else '📝 Internal note (to Ops or IT)',
        horizontal=True,
        key='reply_mode',
    )

    if mode == 'public':
        st.caption(f'Public reply turn {turns_used + 1} of {max_turns}')
    else:
        st.caption(
            f'Internal note {internal_used + 1} of {max_internal_turns} max — '
            'start with "Dear IT" or "Dear Ops" to route correctly'
        )

    # Wait button (only if last internal reply mentions waiting)
    last_internal = None
    for turn in reversed(st.session_state.conversation):
        if turn['role'] in ('ops', 'it'):
            last_internal = turn
            break

    can_wait = False
    if last_internal:
        ctext = last_internal['content'].lower()
        if any(k in ctext for k in ['business day', 'await', 'wait', 'hours', 'within']):
            can_wait = True

    bf = case.get('booking_facts', {})
    is_urgent_24h = False
    dep_str = bf.get('departure_date', '')
    dep_dt = None
    for fmt_str in ('%d-%b-%Y %H:%M', '%d-%b-%y %H:%M'):
        try:
            dep_dt = dt.datetime.strptime(dep_str, fmt_str)
            break
        except (ValueError, TypeError):
            continue
    if dep_dt is not None:
        try:
            delta_hours = (dep_dt - dt.datetime.now()).total_seconds() / 3600
            if 0 <= delta_hours <= 24:
                is_urgent_24h = True
        except Exception:
            pass

    if is_urgent_24h:
        wait_label = '⏳ Skip ahead — request Ops update now (urgent <24h)'
        wait_placeholder = '[Time passes — a few hours. Agent requested Ops to provide an immediate status update given the urgency.]'
    else:
        wait_label = '⏳ Skip ahead — force Ops follow-up (5 business days)'
        wait_placeholder = '[Time passes — 5 business days. Agent did not actively follow up.]'

    if can_wait and mode == 'internal':
        if st.button(wait_label, help='Skip ahead in simulated time. Counts as 1 internal turn.'):
            st.session_state.conversation.append({'role': 'agent_internal', 'content': wait_placeholder, 'addressee': 'ops'})
            st.session_state.internal_turn_count += 1
            client = get_client()
            history = [t for t in st.session_state.conversation if t['role'] in ('agent_internal', 'ops', 'it')]
            with st.spinner('Ops responding after wait...'):
                followup_msg = 'Following up — what is the status? (Urgent, <24h to departure)' if is_urgent_24h else 'Following up — what is the status?'
                ops_reply = get_ops_reply(client, case, followup_msg, history)
                st.session_state.conversation.append({'role': 'ops', 'content': ops_reply})
            st.rerun()

    placeholder_text = (
        'Public reply... (Enter = new line, click Send to submit)'
        if mode == 'public'
        else 'Internal note (start with "Dear IT" or "Dear Ops")... (Enter = new line, click Send to submit)'
    )
    # Use a key that changes after each send so the box clears
    input_key = f'agent_input_{st.session_state.turn_count}_{st.session_state.internal_turn_count}_{mode}'
    agent_reply_text = st.text_area(
        'Your reply',
        key=input_key,
        placeholder=placeholder_text,
        height=140,
        label_visibility='collapsed',
    )
    send_clicked = st.button('Send ▶', type='primary', key=f'send_{input_key}')
    agent_reply = agent_reply_text.strip() if (send_clicked and agent_reply_text and agent_reply_text.strip()) else None

    if agent_reply:
        client = get_client()

        if mode == 'internal':
            addressee = detect_internal_note_addressee(agent_reply)
            st.session_state.conversation.append({
                'role': 'agent_internal',
                'content': agent_reply,
                'addressee': addressee,
            })
            st.session_state.internal_turn_count += 1

            history = [t for t in st.session_state.conversation if t['role'] in ('agent_internal', 'ops', 'it')]
            with st.spinner(f'{addressee.upper()} team responding...'):
                if addressee == 'it':
                    reply = get_it_reply(client, case, agent_reply, history[:-1])
                    st.session_state.conversation.append({'role': 'it', 'content': reply})
                else:
                    reply = get_ops_reply(client, case, agent_reply, history[:-1])
                    st.session_state.conversation.append({'role': 'ops', 'content': reply})

            if st.session_state.internal_turn_count >= max_internal_turns:
                st.warning(f'Internal note limit reached ({max_internal_turns}). Continue with public replies.')

            st.rerun()

        else:  # public
            st.session_state.conversation.append({'role': 'agent_public', 'content': agent_reply})
            st.session_state.turn_count += 1

            # Hit turn cap?
            if st.session_state.turn_count >= max_turns:
                with st.spinner('Wrapping up case…'):
                    verdict = get_final_verdict_structured(client, case, st.session_state.conversation)
                    st.session_state.pending_verdict = verdict
                    st.session_state.case_complete = True
                    log_session(
                        case, st.session_state.agent_email, st.session_state.agent_name,
                        st.session_state.conversation, verdict,
                        st.session_state.feedback_log,
                        st.session_state.session_started_at,
                        case_idx,
                    )
                st.rerun()

            with st.spinner('Customer is typing...'):
                customer_reply = get_customer_reply(client, case, st.session_state.conversation)

            if '[END_CONVERSATION]' in customer_reply:
                customer_reply = customer_reply.replace('[END_CONVERSATION]', '').strip()
                if customer_reply:
                    st.session_state.conversation.append({'role': 'customer', 'content': customer_reply, 'name': customer_name})
                with st.spinner('Customer ended the conversation. Wrapping up case…'):
                    verdict = get_final_verdict_structured(client, case, st.session_state.conversation)
                    st.session_state.pending_verdict = verdict
                    st.session_state.case_complete = True
                    log_session(
                        case, st.session_state.agent_email, st.session_state.agent_name,
                        st.session_state.conversation, verdict,
                        st.session_state.feedback_log,
                        st.session_state.session_started_at,
                        case_idx,
                    )
            else:
                st.session_state.conversation.append({'role': 'customer', 'content': customer_reply, 'name': customer_name})

            st.rerun()
