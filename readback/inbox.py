from contracts import Problem, text_value
from control.show import get_show
from dispatch.ledger import list_seat_sends_after
from editions.lookup import get_edition, issued_seats
from readback.cursor import next_cursor, parse_cursor


def read_inbox(db, show_id, seat, after):
    show = get_show(db, show_id)
    seat = text_value(seat, 'seat')
    after = parse_cursor(after)
    edition = get_edition(db, show.edition_id)
    if seat not in issued_seats(edition):
        raise Problem(404, 'seat_not_found', seat=seat)
    records = list_seat_sends_after(db, show.show_id, seat, after)
    return {'show_id': show.show_id, 'seat': seat, 'items': [row.as_payload() for row in records],
            'next_cursor': next_cursor(after, records)}
