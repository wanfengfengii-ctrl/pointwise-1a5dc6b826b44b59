from contracts import Problem
from editions.lookup import get_issued_card, get_issued_group
from editions.order import order_candidates


def resolve_candidates(edition, selector):
    if selector.keys() == {'group'}:
        _, members = get_issued_group(edition, selector['group'])
        return order_candidates(edition.cards[card_id] for card_id in members)
    if selector.keys() == {'cards'}:
        cards = selector['cards']
        if not isinstance(cards, list) or not cards:
            raise Problem(422, 'invalid_candidate_cards')
        return order_candidates(get_issued_card(edition, reference) for reference in cards)
    raise Problem(422, 'expected_group_or_cards')
