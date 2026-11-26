from collections.abc import Iterable

from editions.payload import IssuedCard


def order_candidates(cards: Iterable[IssuedCard]) -> tuple[IssuedCard, ...]:
    by_id = {card.card_id: card for card in cards}
    return tuple(sorted(by_id.values(), key=lambda card: card.position))
