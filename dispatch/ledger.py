from dataclasses import dataclass

SEND_LEDGER_SCHEMA = '''
CREATE TABLE IF NOT EXISTS show_sends (
    show_id TEXT NOT NULL REFERENCES shows(show_id),
    seq INTEGER NOT NULL CHECK (seq > 0),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    draft_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    text TEXT NOT NULL,
    seat TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    request_id TEXT NOT NULL,
    key_id TEXT,
    PRIMARY KEY (show_id, seq),
    UNIQUE (show_id, card_id),
    UNIQUE (show_id, request_id)
);
CREATE INDEX IF NOT EXISTS show_sends_seat_seq ON show_sends(show_id, seat, seq);
'''


@dataclass(frozen=True)
class SendRecord:
    show_id: str
    seq: int
    edition_id: str
    draft_id: str
    card_id: str
    text: str
    seat: str
    position: int
    request_id: str
    key_id: str | None

    def as_payload(self):
        origin = {'kind': 'manual'} if self.key_id is None else {'kind': 'key', 'key_id': self.key_id}
        return {
            'show_id': self.show_id, 'seq': self.seq, 'card_id': self.card_id,
            'text': self.text, 'seat': self.seat, 'position': self.position,
            'request_id': self.request_id, 'origin': origin,
            'source': {
                'edition_id': self.edition_id, 'draft_id': self.draft_id,
                'card_id': self.card_id,
            },
        }


def append_send(db, show_id, card, request_id, key_id=None):
    seq = db.execute('SELECT COALESCE(MAX(seq), 0) + 1 FROM show_sends WHERE show_id = ?',
                     (show_id,)).fetchone()[0]
    record = SendRecord(show_id, seq, card.edition_id, card.draft_id, card.card_id,
                        card.text, card.seat, card.position, request_id, key_id)
    db.execute('''
        INSERT INTO show_sends(show_id, seq, edition_id, draft_id, card_id, text,
                               seat, position, request_id, key_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (record.show_id, record.seq, record.edition_id, record.draft_id, record.card_id,
          record.text, record.seat, record.position, record.request_id, record.key_id))
    return record


def used_card_ids(db, show_id):
    rows = db.execute('SELECT card_id FROM show_sends WHERE show_id = ?', (show_id,))
    return {row['card_id'] for row in rows}


def list_show_sends(db, show_id):
    rows = db.execute('SELECT * FROM show_sends WHERE show_id = ? ORDER BY seq', (show_id,))
    return [SendRecord(**dict(row)) for row in rows]


def list_seat_sends_after(db, show_id, seat, after):
    if after >= (1 << 63) - 1:
        return []
    rows = db.execute('''
        SELECT * FROM show_sends WHERE show_id = ? AND seat = ? AND seq > ? ORDER BY seq
    ''', (show_id, seat, after))
    return [SendRecord(**dict(row)) for row in rows]
