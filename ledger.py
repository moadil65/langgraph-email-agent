"""A separate write-ahead send ledger to avoid automatic duplicate emails.

After reserving a send, do NOT auto-retry a failed/uncertain send. A crash
between Google accepting it and acknowledging it is inherently ambiguous.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class PendingOrUncertainSend(RuntimeError):
    pass


@contextmanager
def _connect(db: Path):
    conn = sqlite3.connect(str(db), timeout=30)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sends (
            thread_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            gmail_id TEXT,
            error_note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def reserve_send(db: Path, thread_id: str, fingerprint: str):
    """Return (already_sent, gmail_id); otherwise reserve before external send."""
    with _connect(db) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute(
            'SELECT fingerprint, status, gmail_id FROM sends WHERE thread_id = ?',
            (thread_id,),
        ).fetchone()
        if row:
            old_fingerprint, status, gmail_id = row
            if old_fingerprint == fingerprint and status == 'sent':
                return True, gmail_id
            raise PendingOrUncertainSend(
                'This thread already attempted a send. Check Gmail Sent before '
                'doing anything else; the app will not automatically resend.'
            )
        con.execute(
            "INSERT INTO sends (thread_id, fingerprint, status) VALUES (?, ?, 'reserved')",
            (thread_id, fingerprint),
        )
    return False, None


def mark_sent(db: Path, thread_id: str, gmail_id: str):
    with _connect(db) as con:
        con.execute(
            "UPDATE sends SET status = 'sent', gmail_id = ? WHERE thread_id = ?",
            (gmail_id, thread_id),
        )


def mark_uncertain(db: Path, thread_id: str, error: str):
    with _connect(db) as con:
        con.execute(
            "UPDATE sends SET status = 'uncertain', error_note = ? WHERE thread_id = ?",
            (error[:500], thread_id),
        )
