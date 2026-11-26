import json

from contracts import Problem
from scripts.validation import validate_draft

DRAFT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT NOT NULL PRIMARY KEY,
    payload TEXT NOT NULL
);
'''


def put_draft(db, draft_id, cards, groups, order):
    draft = validate_draft(draft_id, cards, groups, order)
    db.execute('''
        INSERT INTO drafts(draft_id, payload) VALUES (?, ?)
        ON CONFLICT(draft_id) DO UPDATE SET payload = excluded.payload
    ''', (draft.draft_id, json.dumps(draft.as_payload(), ensure_ascii=False)))
    return {'draft_id': draft.draft_id, 'order': list(draft.order)}


def load_draft(db, draft_id):
    row = db.execute('SELECT payload FROM drafts WHERE draft_id = ?', (draft_id,)).fetchone()
    if row is None:
        raise Problem(404, 'draft_not_found', draft_id=draft_id)
    return validate_draft(**json.loads(row['payload']))
