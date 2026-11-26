from contracts import Problem, text_value
from control.show import get_show
from dispatch.ledger import list_seat_sends, list_seat_sends_after
from editions.lookup import get_edition, issued_seats
from readback.cursor import (next_cursor, next_insert_cursor, parse_cursor,
                             parse_insert_cursor)


def read_inbox(db, show_id, seat, after):
    show = get_show(db, show_id)
    seat = text_value(seat, 'seat')
    if show.insert_mode:
        covered = parse_insert_cursor(after)
    else:
        after_value = parse_cursor(after)
    edition = get_edition(db, show.edition_id)
    if seat not in issued_seats(edition):
        raise Problem(404, 'seat_not_found', seat=seat)

    if show.insert_mode:
        records = [record for record in list_seat_sends(db, show.show_id, seat)
                   if record.seq not in covered]
        cursor = next_insert_cursor(after, covered, records)
    else:
        records = list_seat_sends_after(db, show.show_id, seat, after_value)
        cursor = next_cursor(after_value, records)
    return {'show_id': show.show_id, 'seat': seat,
            'items': [row.as_payload() for row in records], 'next_cursor': cursor}
