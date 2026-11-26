from dataclasses import dataclass

from control.show import ShowRecord
from dispatch.ledger import SendRecord, list_show_sends
from editions.lookup import get_edition


@dataclass(frozen=True)
class CloseEvidence:
    edition_id: str
    missing_cards: tuple[str, ...]
    sends: tuple[SendRecord, ...]


def reconcile_close(db, show: ShowRecord):
    edition = get_edition(db, show.edition_id)
    sends = tuple(list_show_sends(db, show.show_id))
    sent_ids = {record.card_id for record in sends}
    missing_ids = show.required_cards - sent_ids
    missing = tuple(card_id for card_id in edition.cards if card_id in missing_ids)
    return CloseEvidence(edition.edition_id, missing, sends)
