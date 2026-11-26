from contracts import text_value
from control.show import get_show
from dispatch.candidates import resolve_candidates
from dispatch.ledger import append_send
from dispatch.packs import next_program_seq
from dispatch.receipts import find_send_receipt, request_signature, store_send_receipt
from dispatch.selection import first_unused_card
from editions.lookup import get_edition

_MISSING = object()


def _send(db, show, request_id, signature, selector, key_id=None):
    previous = find_send_receipt(db, show.show_id, request_id, signature)
    if previous is not None:
        return previous
    show.ensure_running()
    edition = get_edition(db, show.edition_id)
    candidates = resolve_candidates(edition, selector)
    card = first_unused_card(db, show.show_id, candidates)
    seq = next_program_seq(db, show.show_id)
    result = append_send(db, show.show_id, card, request_id, key_id, seq=seq).as_payload()
    store_send_receipt(db, show.show_id, request_id, signature, result)
    return result


def send_manual(db, show_id, request_id, group=_MISSING, cards=_MISSING):
    show = get_show(db, show_id)
    request_id = text_value(request_id, 'request_id')
    selector = {name: value for name, value in (('group', group), ('cards', cards))
                if value is not _MISSING}
    return _send(db, show, request_id, request_signature('manual', selector), selector)


def send_from_key(db, show, key_id, group_id, request_id):
    signature = request_signature('key', {'key_id': key_id})
    return _send(db, show, request_id, signature, {'group': group_id}, key_id)
