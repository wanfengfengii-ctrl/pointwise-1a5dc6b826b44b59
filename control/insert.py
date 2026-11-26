import json

from contracts import Problem, text_value
from control.show import get_show
from dispatch.ledger import append_send, list_show_sends, used_card_ids
from dispatch.packs import (find_show_pack, get_pack, list_pack_cards,
                            next_program_seq, offline_request_id,
                            pending_pack_card_ids)
from editions.lookup import get_edition, get_issued_card


def _validate_card_list(value, field):
    if not isinstance(value, list) or not (1 <= len(value) <= 4):
        raise Problem(422, 'invalid_pack_cards', field=field)
    card_ids = []
    for item in value:
        card_ids.append(text_value(item, field))
    if len(set(card_ids)) != len(card_ids):
        raise Problem(422, 'duplicate_pack_card', field=field)
    return card_ids


def _validate_played(value):
    if not isinstance(value, list):
        raise Problem(422, 'invalid_played')
    return [text_value(item, 'played_card') for item in value]


def _reserve_payload(db, show, pack_id, rows, edition):
    cards = []
    for row in rows:
        card = get_issued_card(edition, row['card_id'])
        item = card.as_payload()
        item['seq'] = row['seq']
        cards.append(item)
    return {'show_id': show.show_id, 'pack_id': pack_id,
            'edition_id': edition.edition_id, 'cards': cards}


def _return_payload(db, show_id, pack_id):
    sends = [record.as_payload() for record in list_show_sends(db, show_id)
             if record.pack_id == pack_id]
    return {'show_id': show_id, 'pack_id': pack_id, 'sends': sends}


def insert_reserve(db, show_id, pack_id, cards):
    show = get_show(db, show_id)
    pack_id = text_value(pack_id, 'pack_id')
    card_ids = _validate_card_list(cards, 'cards')
    edition = get_edition(db, show.edition_id)
    card_objects = [get_issued_card(edition, card_id) for card_id in card_ids]

    existing = find_show_pack(db, show.show_id)
    if existing is not None:
        rows = list_pack_cards(db, show.show_id, existing['pack_id'])
        original_ids = [row['card_id'] for row in rows]
        if existing['pack_id'] != pack_id or original_ids != card_ids:
            raise Problem(409, 'insert_pack_conflict',
                          pack_id=existing['pack_id'])
        return _reserve_payload(db, show, pack_id, rows, edition)

    show.ensure_running()
    if not show.insert_mode:
        raise Problem(409, 'insert_mode_disabled', show_id=show.show_id)

    unavailable = used_card_ids(db, show.show_id) | pending_pack_card_ids(db, show.show_id)
    if any(card_id in unavailable for card_id in card_ids):
        raise Problem(409, 'card_already_sent', show_id=show.show_id)

    start_seq = next_program_seq(db, show.show_id)
    db.execute('''
        INSERT INTO insert_packs(show_id, pack_id, status, played)
        VALUES (?, ?, 'pending', NULL)
    ''', (show.show_id, pack_id))
    rows = []
    for ordinal, card in enumerate(card_objects):
        seq = start_seq + ordinal
        db.execute('''
            INSERT INTO insert_pack_cards(show_id, pack_id, ordinal, seq, card_id, state)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (show.show_id, pack_id, ordinal, seq, card.card_id))
        rows.append({'ordinal': ordinal, 'seq': seq, 'card_id': card.card_id})
    return _reserve_payload(db, show, pack_id, rows, edition)


def insert_return(db, show_id, pack_id, played):
    show = get_show(db, show_id)
    pack_id = text_value(pack_id, 'pack_id')
    played_ids = _validate_played(played)

    pack = get_pack(db, show.show_id, pack_id)
    if pack is None:
        raise Problem(409, 'insert_pack_not_found', pack_id=pack_id)
    rows = list_pack_cards(db, show.show_id, pack_id)
    original_ids = [row['card_id'] for row in rows]

    if pack['status'] == 'returned':
        recorded = json.loads(pack['played'])
        if recorded != played_ids:
            raise Problem(409, 'insert_return_conflict', pack_id=pack_id)
        return _return_payload(db, show.show_id, pack_id)

    show.ensure_running()
    if played_ids != original_ids[:len(played_ids)]:
        raise Problem(409, 'invalid_played_prefix', pack_id=pack_id)

    edition = get_edition(db, show.edition_id)
    for ordinal, card_id in enumerate(played_ids):
        row = rows[ordinal]
        card = get_issued_card(edition, card_id)
        request_id = offline_request_id(pack_id, ordinal)
        append_send(db, show.show_id, card, request_id, None,
                    seq=row['seq'], pack_id=pack_id)
        db.execute('''
            UPDATE insert_pack_cards SET state = 'returned'
            WHERE show_id = ? AND pack_id = ? AND ordinal = ?
        ''', (show.show_id, pack_id, ordinal))

    db.execute('''
        UPDATE insert_pack_cards SET state = 'released'
        WHERE show_id = ? AND pack_id = ? AND ordinal >= ?
    ''', (show.show_id, pack_id, len(played_ids)))
    db.execute('''
        UPDATE insert_packs SET status = 'returned', played = ?
        WHERE show_id = ? AND pack_id = ?
    ''', (json.dumps(played_ids, ensure_ascii=False), show.show_id, pack_id))
    return _return_payload(db, show.show_id, pack_id)
