"""
Anonymize PII before sending ticket data to LLM.
Strips emails, phone numbers, full names, booking codes.
Preserves conversational content needed for analysis.
"""
import re


# Common patterns
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PHONE_RE = re.compile(r'(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}')
URL_RE = re.compile(r'https?://\S+')
# Booking refs like 12GO123456, ABC-123-456
BOOKING_RE = re.compile(r'\b(?:12GO|BK|REF)[\s\-]?\d{4,}\b', re.IGNORECASE)
# Credit card-ish numbers
CC_RE = re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b')


def anonymize_text(text: str) -> str:
    """Replace PII patterns with placeholders."""
    if not text:
        return text

    text = EMAIL_RE.sub('[EMAIL]', text)
    text = CC_RE.sub('[CARD_NUMBER]', text)
    text = BOOKING_RE.sub('[BOOKING_REF]', text)
    text = URL_RE.sub('[URL]', text)
    # Phone after CC to avoid grabbing card digits
    text = PHONE_RE.sub('[PHONE]', text)

    return text


def anonymize_name(full_name: str) -> str:
    """Reduce full name to first name only for natural conversation flow."""
    if not full_name:
        return '[Customer]'
    parts = full_name.strip().split()
    if not parts:
        return '[Customer]'
    # Keep first name only, anonymize surname
    return parts[0]


def anonymize_ticket_data(ticket: dict) -> dict:
    """Anonymize a parsed ticket structure."""
    anonymized = {
        'ticket_id': ticket.get('ticket_id'),
        'subject': anonymize_text(ticket.get('subject', '')),
        'customer_name': anonymize_name(ticket.get('customer_name', '')),
        'csat_score': ticket.get('csat_score'),
        'csat_comment': anonymize_text(ticket.get('csat_comment', '')),
        'messages': [
            {
                'author_role': m.get('author_role'),
                'body': anonymize_text(m.get('body', '')),
                'created_at': m.get('created_at'),
            }
            for m in ticket.get('messages', [])
        ],
    }
    return anonymized


if __name__ == '__main__':
    # Quick test
    sample = """Hi John Smith, your booking 12GO123456 is confirmed.
    Contact me at agent@12go.asia or +66 12 345 6789.
    Tracking link: https://12go.asia/track/abc"""
    print(anonymize_text(sample))
