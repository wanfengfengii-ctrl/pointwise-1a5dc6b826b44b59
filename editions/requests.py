ISSUE_REQUEST_SCHEMA = '''
CREATE TABLE IF NOT EXISTS issue_requests (
    request_id TEXT NOT NULL PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES drafts(draft_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id)
);
'''


def find_issue_request(db, request_id):
    return db.execute('SELECT draft_id, edition_id FROM issue_requests WHERE request_id = ?',
                      (request_id,)).fetchone()


def record_issue_request(db, request_id, draft_id, edition_id):
    db.execute('INSERT INTO issue_requests(request_id, draft_id, edition_id) VALUES (?, ?, ?)',
               (request_id, draft_id, edition_id))
