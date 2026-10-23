"""Small, deterministic security helpers; these do not ask the LLM to authorize sends."""

import hashlib
import json

from email_validator import EmailNotValidError, validate_email


def checked_recipient(raw: str) -> str:
    """Accept exactly one mailbox; reject newlines and header injection."""
    if not isinstance(raw, str) or any(ch in raw for ch in ('\r', '\n')):
        raise ValueError('Recipient must be a single email address.')
    candidate = raw.strip()
    if not candidate or ',' in candidate or ';' in candidate:
        raise ValueError('Enter exactly one recipient email address.')
    try:
        return validate_email(candidate, check_deliverability=False).normalized
    except EmailNotValidError as error:
        raise ValueError(f'Invalid recipient: {error}') from error


def checked_mail_fields(recipient: str, subject: str, body: str) -> None:
    checked_recipient(recipient)
    if not subject or not subject.strip() or any(ch in subject for ch in ('\r', '\n')):
        raise ValueError('Email subject must be one nonempty line.')
    if not body or not body.strip():
        raise ValueError('Email body cannot be empty.')


def mail_fingerprint(recipient: str, subject: str, body: str) -> str:
    """Fingerprint exactly the user-approved fields (no LLM modifications afterward)."""
    checked_mail_fields(recipient, subject, body)
    payload = json.dumps(
        {'recipient': recipient, 'subject': subject, 'body': body},
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
