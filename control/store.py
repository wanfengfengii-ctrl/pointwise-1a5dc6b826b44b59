import sqlite3
from contextlib import closing, contextmanager


def connect_database(database):
    db = sqlite3.connect(database, isolation_level=None, timeout=10.0)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize_database(database, schemas):
    with closing(connect_database(database)) as db:
        db.execute('PRAGMA journal_mode = WAL').fetchone()
        script = '\n'.join(('BEGIN IMMEDIATE;', *schemas, 'COMMIT;'))
        db.executescript(script)


@contextmanager
def _transaction(db, begin):
    db.execute(begin)
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def write_transaction(db):
    return _transaction(db, 'BEGIN IMMEDIATE')


def read_transaction(db):
    return _transaction(db, 'BEGIN')
