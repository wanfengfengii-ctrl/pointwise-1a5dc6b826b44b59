from contracts import Problem, text_value


def parse_groups(values):
    if not isinstance(values, dict):
        raise Problem(422, 'invalid_groups')
    groups = {}
    for name, members in values.items():
        group_id = text_value(name, 'group_id')
        if not isinstance(members, list) or not members:
            raise Problem(422, 'invalid_group_members', group_id=group_id)
        card_ids = tuple(text_value(member, 'group_member') for member in members)
        if len(set(card_ids)) != len(card_ids):
            raise Problem(422, 'duplicate_group_member', group_id=group_id)
        groups[group_id] = card_ids
    return groups


def validate_group_references(groups, card_ids):
    for group_id, members in groups.items():
        unknown = [card_id for card_id in members if card_id not in card_ids]
        if unknown:
            raise Problem(422, 'unknown_group_card', group_id=group_id, card_ids=unknown)
