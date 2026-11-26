import json
from dataclasses import dataclass

ARCHIVE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS archives (
    archive_no INTEGER PRIMARY KEY,
    archive_id TEXT NOT NULL UNIQUE,
    show_id TEXT NOT NULL UNIQUE REFERENCES shows(show_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    sends TEXT NOT NULL
);
'''


@dataclass(frozen=True)
class ArchiveRecord:
    archive_id: str
    show_id: str
    edition_id: str
    sends: tuple[dict, ...]

    def as_payload(self):
        return {'archive_id': self.archive_id, 'show_id': self.show_id,
                'edition_id': self.edition_id, 'sends': list(self.sends)}


def store_archive(db, show_id, edition_id, sends):
    number = db.execute('SELECT COALESCE(MAX(archive_no), 0) + 1 FROM archives').fetchone()[0]
    record = ArchiveRecord(f'C{number}', show_id, edition_id, tuple(sends))
    db.execute('''
        INSERT INTO archives(archive_no, archive_id, show_id, edition_id, sends)
        VALUES (?, ?, ?, ?, ?)
    ''', (number, record.archive_id, show_id, edition_id,
          json.dumps(record.sends, ensure_ascii=False)))
    return record


def _decode(row):
    if row is None:
        return None
    return ArchiveRecord(row['archive_id'], row['show_id'], row['edition_id'],
                         tuple(json.loads(row['sends'])))


def get_archive_by_show(db, show_id):
    return _decode(db.execute('SELECT * FROM archives WHERE show_id = ?', (show_id,)).fetchone())


def get_archive_by_number(db, archive_id):
    return _decode(db.execute('SELECT * FROM archives WHERE archive_id = ?', (archive_id,)).fetchone())
