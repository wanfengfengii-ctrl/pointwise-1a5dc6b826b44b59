import json
from dataclasses import dataclass

from contracts import Problem, text_value
from control.bindings import read_bindings, store_bindings, validate_bindings
from editions.lookup import get_edition, get_issued_card

SHOW_SCHEMA = '''
CREATE TABLE IF NOT EXISTS shows (
    show_id TEXT NOT NULL PRIMARY KEY,
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    required_cards TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('running', 'closed'))
);
'''


@dataclass(frozen=True)
class ShowRecord:
    show_id: str
    edition_id: str
    required_cards: frozenset[str]
    state: str

    def ensure_running(self):
        if self.state != 'running':
            raise Problem(409, 'show_closed', show_id=self.show_id)


def _find_show(db, show_id):
    row = db.execute('SELECT * FROM shows WHERE show_id = ?', (show_id,)).fetchone()
    if row is None:
        return None
    return ShowRecord(row['show_id'], row['edition_id'],
                      frozenset(json.loads(row['required_cards'])), row['state'])


def get_show(db, show_id):
    show_id = text_value(show_id, 'show_id')
    show = _find_show(db, show_id)
    if show is None:
        raise Problem(404, 'show_not_found', show_id=show_id)
    return show


def open_show(db, show_id, edition_id, bindings, required_cards):
    show_id = text_value(show_id, 'show_id')
    edition = get_edition(db, edition_id)
    keys = validate_bindings(edition, bindings)
    if not isinstance(required_cards, list):
        raise Problem(422, 'invalid_required_cards')
    required = frozenset(get_issued_card(edition, ref).card_id for ref in required_cards)
    previous = _find_show(db, show_id)
    if previous is None:
        db.execute('INSERT INTO shows VALUES (?, ?, ?, ?)',
                   (show_id, edition.edition_id, json.dumps(sorted(required)), 'running'))
        store_bindings(db, show_id, keys)
    else:
        previous.ensure_running()
        if (previous.edition_id != edition.edition_id or previous.required_cards != required
                or read_bindings(db, show_id) != keys):
            raise Problem(409, 'show_configuration_conflict', show_id=show_id)
    return {'show_id': show_id, 'edition_id': edition.edition_id, 'state': 'running'}


def mark_show_closed(db, show_id):
    updated = db.execute("UPDATE shows SET state = 'closed' WHERE show_id = ? AND state = 'running'",
                         (show_id,))
    if updated.rowcount != 1:
        raise Problem(409, 'show_closed', show_id=show_id)
