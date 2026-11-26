from contracts import Problem, text_value
from control.show import get_show, mark_show_closed
from readback.archive import get_archive_by_show, store_archive
from readback.reconciliation import reconcile_close

CLOSE_REQUEST_SCHEMA = '''
CREATE TABLE IF NOT EXISTS close_requests (
    request_id TEXT NOT NULL PRIMARY KEY,
    show_id TEXT NOT NULL REFERENCES archives(show_id)
);
'''


def close_show(db, show_id, request_id):
    show_id = text_value(show_id, 'show_id')
    request_id = text_value(request_id, 'request_id')
    old = db.execute('SELECT show_id FROM close_requests WHERE request_id = ?', (request_id,)).fetchone()
    if old is not None and old['show_id'] != show_id:
        raise Problem(409, 'close_request_conflict')
    show = get_show(db, show_id)
    archive = get_archive_by_show(db, show.show_id)
    if archive is None:
        show.ensure_running()
        evidence = reconcile_close(db, show)
        if evidence.missing_cards:
            raise Problem(409, 'required_cards_missing', missing_cards=list(evidence.missing_cards))
        archive = store_archive(db, show.show_id, evidence.edition_id,
                                (record.as_payload() for record in evidence.sends))
        mark_show_closed(db, show.show_id)
    if old is None:
        db.execute('INSERT INTO close_requests(request_id, show_id) VALUES (?, ?)',
                   (request_id, show.show_id))
    return archive.as_payload()
