from dataclasses import asdict, dataclass

from contracts import Problem, require_fields, text_value


@dataclass(frozen=True)
class DraftCard:
    card_id: str
    text: str
    seat: str

    def as_payload(self):
        return asdict(self)


def parse_cards(values):
    if not isinstance(values, list) or not values:
        raise Problem(422, 'invalid_cards')
    cards = {}
    for value in values:
        require_fields(value, ('card_id', 'text', 'seat'))
        card = DraftCard(text_value(value['card_id'], 'card_id'),
                         text_value(value['text'], 'text'),
                         text_value(value['seat'], 'seat'))
        if card.card_id in cards:
            raise Problem(422, 'duplicate_card', card_id=card.card_id)
        cards[card.card_id] = card
    return cards
