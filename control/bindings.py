from contracts import Problem, text_value
from editions.lookup import get_issued_group

BINDING_SCHEMA = '''
CREATE TABLE IF NOT EXISTS key_bindings (
    show_id TEXT NOT NULL REFERENCES shows(show_id),
    key_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    PRIMARY KEY (show_id, key_id)
);
'''


def validate_bindings(edition, bindings):
    if not isinstance(bindings, dict):
        raise Problem(422, 'invalid_bindings')
    result = {}
    for key, reference in bindings.items():
        key_id = text_value(key, 'key_id')
        group_id, _ = get_issued_group(edition, reference)
        result[key_id] = group_id
    return result


def store_bindings(db, show_id, bindings):
    db.executemany('INSERT INTO key_bindings(show_id, key_id, group_id) VALUES (?, ?, ?)',
                   ((show_id, key_id, group_id) for key_id, group_id in bindings.items()))


def read_bindings(db, show_id):
    rows = db.execute('SELECT key_id, group_id FROM key_bindings WHERE show_id = ?', (show_id,))
    return {row['key_id']: row['group_id'] for row in rows}


def get_bound_group(db, show_id, key_id):
    row = db.execute('SELECT group_id FROM key_bindings WHERE show_id = ? AND key_id = ?',
                     (show_id, key_id)).fetchone()
    if row is None:
        raise Problem(422, 'unbound_key', key_id=key_id)
    return row['group_id']
