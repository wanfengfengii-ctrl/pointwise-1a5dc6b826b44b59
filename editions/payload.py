import json
from dataclasses import dataclass

from scripts.validation import ValidatedDraft


@dataclass(frozen=True)
class IssuedCard:
    edition_id: str
    draft_id: str
    card_id: str
    text: str
    seat: str
    position: int

    def as_payload(self):
        return {
            'card_id': self.card_id, 'text': self.text, 'seat': self.seat,
            'position': self.position,
            'source': {
                'edition_id': self.edition_id, 'draft_id': self.draft_id,
                'card_id': self.card_id,
            },
        }


@dataclass(frozen=True)
class IssuedEdition:
    edition_id: str
    draft_id: str
    cards: dict[str, IssuedCard]
    groups: dict[str, tuple[str, ...]]

    def as_payload(self):
        return {
            'edition_id': self.edition_id, 'draft_id': self.draft_id,
            'order': list(self.cards),
            'cards': [card.as_payload() for card in self.cards.values()],
            'groups': {name: list(members) for name, members in self.groups.items()},
        }


def freeze_edition(edition_id: str, draft: ValidatedDraft):
    cards = {}
    for position, card_id in enumerate(draft.order, start=1):
        card = draft.cards[card_id]
        cards[card_id] = IssuedCard(edition_id, draft.draft_id, card_id,
                                    card.text, card.seat, position)
    return IssuedEdition(edition_id, draft.draft_id, cards, dict(draft.groups))


def encode_edition(edition):
    return json.dumps(edition.as_payload(), ensure_ascii=False)


def decode_edition(payload):
    value = json.loads(payload)
    edition_id, draft_id = value['edition_id'], value['draft_id']
    cards = {}
    for data in value['cards']:
        card_id = data['card_id']
        cards[card_id] = IssuedCard(edition_id, draft_id, card_id, data['text'],
                                    data['seat'], data['position'])
    groups = {name: tuple(members) for name, members in value['groups'].items()}
    return IssuedEdition(edition_id, draft_id, cards, groups)
