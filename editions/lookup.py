from contracts import Problem, require_fields, text_value
from editions.payload import decode_edition


def get_edition(db, edition_id):
    edition_id = text_value(edition_id, 'edition_id')
    row = db.execute('SELECT payload FROM editions WHERE edition_id = ?',
                     (edition_id,)).fetchone()
    if row is None:
        raise Problem(404, 'edition_not_found', edition_id=edition_id)
    return decode_edition(row['payload'])


def _local_id(edition, reference, field):
    if isinstance(reference, dict):
        require_fields(reference, ('edition_id', field))
        edition_id = text_value(reference['edition_id'], 'edition_id')
        if edition_id != edition.edition_id:
            raise Problem(422, 'foreign_edition', edition_id=edition_id)
        reference = reference[field]
    return text_value(reference, field)


def get_issued_card(edition, reference):
    card_id = _local_id(edition, reference, 'card_id')
    if card_id not in edition.cards:
        raise Problem(422, 'unknown_card', card_id=card_id)
    return edition.cards[card_id]


def get_issued_group(edition, reference):
    group_id = _local_id(edition, reference, 'group_id')
    if group_id not in edition.groups:
        raise Problem(422, 'unknown_group', group_id=group_id)
    return group_id, edition.groups[group_id]


def issued_seats(edition):
    return {card.seat for card in edition.cards.values()}
