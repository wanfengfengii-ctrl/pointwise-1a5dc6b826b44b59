KEY_REQUEST_SCHEMA = '''
CREATE TABLE IF NOT EXISTS key_requests (
    show_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    PRIMARY KEY (show_id, request_id),
    FOREIGN KEY (show_id, key_id) REFERENCES key_bindings(show_id, key_id),
    FOREIGN KEY (show_id, request_id) REFERENCES send_receipts(show_id, request_id)
);
'''


def find_key_request(db, show_id, request_id):
    row = db.execute('SELECT key_id FROM key_requests WHERE show_id = ? AND request_id = ?',
                     (show_id, request_id)).fetchone()
    return None if row is None else row['key_id']


def record_key_request(db, show_id, request_id, key_id):
    db.execute('INSERT INTO key_requests(show_id, request_id, key_id) VALUES (?, ?, ?)',
               (show_id, request_id, key_id))
