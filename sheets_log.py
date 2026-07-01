"""
sheets_log.py — v9.7

Appends one row per completed case to the `csat_trainer_sessions` Google Sheet.

Reads credentials and the sheet URL from Streamlit secrets:

    [gcp_service_account]
    type = "service_account"
    project_id = "csat-trainer"
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    client_email = "csat-trainer-bot@csat-trainer.iam.gserviceaccount.com"
    client_id = "..."
    ... (everything from the downloaded JSON key) ...

    [sheets]
    url = "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit"

Design notes:
- The connection is cached with st.cache_resource so we authenticate once.
- The header row is created automatically if the sheet is empty.
- All public functions are safe to call; trainer.py wraps them in try/except
  so a Sheets problem can never break a training session.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# Column order — MUST stay in sync with HEADER below and with the dict
# passed from trainer.log_session().
HEADER = [
    'timestamp',
    'session_id',
    'email',
    'role',
    'case_id',
    'csat_score',
    'case_score_100',
    'key_gaps',
    'turn_count',
    'duration_sec',
    'anti_cheat_verdict',
    'app_version',
]

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


@st.cache_resource(show_spinner=False)
def _get_worksheet():
    """Authenticate and return the first worksheet.

    Cached so we only authenticate once per app session. Header creation is
    handled separately in _ensure_header() so it runs on every append rather
    than only on a cache miss.
    """
    creds_info = dict(st.secrets['gcp_service_account'])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet_url = st.secrets['sheets']['url']
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.sheet1


def _ensure_header(worksheet):
    """Make sure row 1 is the header. Idempotent and cheap (one read).

    - Empty sheet  -> append the header as row 1.
    - First row is not the header (e.g. data landed in row 1) -> insert the
      header above it so nothing is lost.
    - First row already matches -> do nothing.
    """
    first_row = worksheet.row_values(1)
    if first_row == HEADER:
        return
    if not worksheet.get_all_values():
        worksheet.append_row(HEADER, value_input_option='RAW')
    else:
        worksheet.insert_row(HEADER, index=1, value_input_option='RAW')


def append_session_row(row_dict):
    """Append one completed-case row. `row_dict` keys must match HEADER.

    Missing keys are written as empty strings so a schema mismatch degrades
    gracefully instead of raising.
    """
    worksheet = _get_worksheet()
    _ensure_header(worksheet)
    row = [row_dict.get(col, '') for col in HEADER]
    worksheet.append_row(row, value_input_option='RAW')


def get_completed_case_ids(email):
    """v9.7: Return the set of case_id ints this email has already completed
    (all-time). Used for resume: skip finished cases on login.

    Safe by design — any error returns an empty set so login never breaks;
    worst case the agent simply starts from Case 1.
    """
    email = (email or '').strip().lower()
    done = set()
    try:
        worksheet = _get_worksheet()
        _ensure_header(worksheet)
        records = worksheet.get_all_records()  # each row as {header: value}
    except Exception:
        return done
    for r in records:
        if str(r.get('email', '')).strip().lower() == email:
            try:
                done.add(int(r.get('case_id')))
            except (TypeError, ValueError):
                pass
    return done
