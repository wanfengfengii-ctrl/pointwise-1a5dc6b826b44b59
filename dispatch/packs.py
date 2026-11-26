PACK_SCHEMA = '''
CREATE TABLE IF NOT EXISTS insert_packs (
    show_id TEXT NOT NULL REFERENCES shows(show_id),
    pack_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'returned')),
    played TEXT,
    PRIMARY KEY (show_id, pack_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS insert_packs_one_show ON insert_packs(show_id);

CREATE TABLE IF NOT EXISTS insert_pack_cards (
    show_id TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    seq INTEGER NOT NULL CHECK (seq > 0),
    card_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'returned', 'released')),
    PRIMARY KEY (show_id, pack_id, ordinal),
    UNIQUE (show_id, seq),
    FOREIGN KEY (show_id, pack_id) REFERENCES insert_packs(show_id, pack_id)
);
CREATE INDEX IF NOT EXISTS insert_pack_cards_pending
    ON insert_pack_cards(show_id, state, card_id);
'''


def find_show_pack(db, show_id):
    return db.execute('''
        SELECT show_id, pack_id, status, played
        FROM insert_packs WHERE show_id = ?
    ''', (show_id,)).fetchone()


def get_pack(db, show_id, pack_id):
    return db.execute('''
        SELECT show_id, pack_id, status, played
        FROM insert_packs WHERE show_id = ? AND pack_id = ?
    ''', (show_id, pack_id)).fetchone()


def list_pack_cards(db, show_id, pack_id):
    return db.execute('''
        SELECT ordinal, seq, card_id, state
        FROM insert_pack_cards
        WHERE show_id = ? AND pack_id = ?
        ORDER BY ordinal
    ''', (show_id, pack_id)).fetchall()


def pending_pack_card_ids(db, show_id):
    rows = db.execute('''
        SELECT card_id FROM insert_pack_cards
        WHERE show_id = ? AND state = 'pending'
    ''', (show_id,))
    return {row['card_id'] for row in rows}


def pending_pack_id(db, show_id):
    row = db.execute('''
        SELECT pack_id FROM insert_packs
        WHERE show_id = ? AND status = 'pending'
        LIMIT 1
    ''', (show_id,)).fetchone()
    return None if row is None else row['pack_id']


def has_pending_pack(db, show_id):
    return pending_pack_id(db, show_id) is not None


def next_program_seq(db, show_id):
    row = db.execute('''
        SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq
        FROM (
            SELECT seq FROM show_sends WHERE show_id = ?
            UNION ALL
            SELECT seq FROM insert_pack_cards WHERE show_id = ?
        )
    ''', (show_id, show_id)).fetchone()
    return row['next_seq']


def offline_request_id(pack_id, ordinal):
    # A namespaced surrogate keeps the existing NOT NULL/UNIQUE receipt columns.
    return f'\\u001fpointwise-offline\\u001f{pack_id}\\u001f{ordinal}'
