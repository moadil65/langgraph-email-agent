import sqlite3
import tempfile
import unittest
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1]))
from security import checked_recipient, checked_mail_fields, mail_fingerprint
from ledger import PendingOrUncertainSend, mark_sent, mark_uncertain, reserve_send


class SecurityTests(unittest.TestCase):
    def test_address_and_header_validation(self):
        self.assertEqual(checked_recipient('  STUDENT@EXAMPLE.COM  '), 'STUDENT@example.com')
        for addr in ['one@example.com, two@example.com', 'someone@example.com\r\nBcc: bad@example.com', 'bad', '']:
            with self.assertRaises(ValueError):
                checked_recipient(addr)
        with self.assertRaises(ValueError):
            checked_mail_fields('me@example.com', 'Subject\r\nBcc: x@x.com', 'hello')

    def test_approval_exact_match(self):
        signature = mail_fingerprint('student@example.com', 'Hello', 'Body')
        self.assertNotEqual(signature, mail_fingerprint('student@example.com', 'Hello', 'Body!'))
        self.assertNotEqual(signature, mail_fingerprint('other@example.com', 'Hello', 'Body'))

    def test_send_ledger_blocks_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'ledger.sqlite'
            self.assertEqual(reserve_send(db, 'thread1', 'abc'), (False, None))
            with self.assertRaises(PendingOrUncertainSend):
                reserve_send(db, 'thread1', 'abc')
            mark_sent(db, 'thread1', 'gmail-id-1')
            self.assertEqual(reserve_send(db, 'thread1', 'abc'), (True, 'gmail-id-1'))
            with self.assertRaises(PendingOrUncertainSend):
                reserve_send(db, 'thread1', 'different')
            reserve_send(db, 'thread2', 'xyz')
            mark_uncertain(db, 'thread2', 'network unavailable')
            with self.assertRaises(PendingOrUncertainSend):
                reserve_send(db, 'thread2', 'xyz')


if __name__ == '__main__':
    unittest.main()
