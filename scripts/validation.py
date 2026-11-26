from dataclasses import dataclass

from contracts import Problem, text_value
from scripts.cards import DraftCard, parse_cards
from scripts.groups import parse_groups, validate_group_references


@dataclass(frozen=True)
class ValidatedDraft:
    draft_id: str
    cards: dict[str, DraftCard]
    groups: dict[str, tuple[str, ...]]
    order: tuple[str, ...]

    def as_payload(self):
        return {
            'draft_id': self.draft_id,
            'cards': [self.cards[card_id].as_payload() for card_id in self.order],
            'groups': {name: list(members) for name, members in self.groups.items()},
            'order': list(self.order),
        }


def validate_issue_order(values, card_ids):
    if not isinstance(values, list):
        raise Problem(422, 'invalid_issue_order')
    order = tuple(text_value(card_id, 'order_card') for card_id in values)
    if len(order) != len(card_ids) or set(order) != set(card_ids):
        raise Problem(422, 'invalid_issue_order')
    return order


def validate_draft(draft_id, cards, groups, order):
    draft_id = text_value(draft_id, 'draft_id')
    parsed_cards = parse_cards(cards)
    parsed_groups = parse_groups(groups)
    validate_group_references(parsed_groups, parsed_cards)
    issue_order = validate_issue_order(order, parsed_cards)
    return ValidatedDraft(draft_id, parsed_cards, parsed_groups, issue_order)
