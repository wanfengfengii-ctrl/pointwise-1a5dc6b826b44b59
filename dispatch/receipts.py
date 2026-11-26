import json

from contracts import Problem

SEND_RECEIPT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS send_receipts (
    show_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    signature TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (show_id, request_id),
    FOREIGN KEY (show_id, seq) REFERENCES show_sends(show_id, seq)
);
'''


def request_signature(entry, arguments):
    return json.dumps([entry, arguments], sort_keys=True, separators=(',', ':'))


def find_send_receipt(db, show_id, request_id, signature):
    row = db.execute('''
        SELECT signature, payload FROM send_receipts WHERE show_id = ? AND request_id = ?
    ''', (show_id, request_id)).fetchone()
    if row is None:
        return None
    if row['signature'] != signature:
        raise Problem(409, 'send_request_conflict')
    return json.loads(row['payload'])


def store_send_receipt(db, show_id, request_id, signature, result):
    db.execute('''
        INSERT INTO send_receipts(show_id, request_id, signature, seq, payload)
        VALUES (?, ?, ?, ?, ?)
    ''', (show_id, request_id, signature, result['seq'], json.dumps(result, ensure_ascii=False)))
