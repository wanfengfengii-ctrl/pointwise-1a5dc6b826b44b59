from contracts import Problem
from dispatch.ledger import used_card_ids


def first_unused_card(db, show_id, candidates):
    used = used_card_ids(db, show_id)
    for card in candidates:
        if card.card_id not in used:
            return card
    raise Problem(409, 'no_unused_card', show_id=show_id)
