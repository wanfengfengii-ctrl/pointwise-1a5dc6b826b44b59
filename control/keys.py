from contracts import Problem, text_value
from control.bindings import get_bound_group
from control.requests import find_key_request, record_key_request
from control.show import get_show
from dispatch.receipts import find_send_receipt, request_signature
from dispatch.send import send_from_key


def send_key(db, show_id, key_id, request_id):
    show = get_show(db, show_id)
    show.ensure_running()
    key_id = text_value(key_id, 'key_id')
    request_id = text_value(request_id, 'request_id')
    previous_key = find_key_request(db, show.show_id, request_id)
    if previous_key is not None and previous_key != key_id:
        raise Problem(409, 'send_request_conflict')
    signature = request_signature('key', {'key_id': key_id})
    previous = find_send_receipt(db, show.show_id, request_id, signature)
    if previous is not None:
        return previous
    group_id = get_bound_group(db, show.show_id, key_id)
    result = send_from_key(db, show, key_id, group_id, request_id)
    record_key_request(db, show.show_id, request_id, key_id)
    return result
