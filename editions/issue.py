from contracts import Problem, text_value
from editions.lookup import get_edition
from editions.payload import encode_edition, freeze_edition
from editions.requests import find_issue_request, record_issue_request
from scripts.drafts import load_draft

EDITION_SCHEMA = '''
CREATE TABLE IF NOT EXISTS editions (
    edition_no INTEGER PRIMARY KEY,
    edition_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL
);
'''


def issue_edition(db, draft_id, request_id):
    draft_id = text_value(draft_id, 'draft_id')
    request_id = text_value(request_id, 'request_id')
    previous = find_issue_request(db, request_id)
    if previous is not None:
        if previous['draft_id'] != draft_id:
            raise Problem(409, 'issue_request_conflict')
        return get_edition(db, previous['edition_id']).as_payload()

    draft = load_draft(db, draft_id)
    number = db.execute('SELECT COALESCE(MAX(edition_no), 0) + 1 FROM editions').fetchone()[0]
    edition = freeze_edition(f'E{number}', draft)
    db.execute('INSERT INTO editions(edition_no, edition_id, payload) VALUES (?, ?, ?)',
               (number, edition.edition_id, encode_edition(edition)))
    record_issue_request(db, request_id, draft.draft_id, edition.edition_id)
    return edition.as_payload()
