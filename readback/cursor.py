import base64
import binascii
import json

from contracts import Problem

_CURSOR_PREFIX = 'ic1.'


def parse_cursor(value):
    if type(value) is not int or value < 0:
        raise Problem(422, 'invalid_cursor')
    return value


def next_cursor(after, records):
    return records[-1].seq if records else after


def parse_insert_cursor(value):
    """Return the seq set covered by an insert-show opaque cursor."""
    if value is None:
        return frozenset()
    # Compatibility with the shared test helper's original zero baseline.
    if type(value) is int and value == 0:
        return frozenset()
    if not isinstance(value, str) or not value.startswith(_CURSOR_PREFIX) or not value[len(_CURSOR_PREFIX):]:
        raise Problem(422, 'invalid_cursor')
    token = value[len(_CURSOR_PREFIX):]
    try:
        padded = token + '=' * (-len(token) % 4)
        raw = base64.b64decode(padded.encode('ascii'), altchars=b'-_', validate=True)
        decoded = json.loads(raw.decode('utf-8'))
        if (not isinstance(decoded, list)
                or any(type(seq) is not int or seq <= 0 for seq in decoded)):
            raise ValueError('invalid cursor payload')
        return frozenset(decoded)
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as error:
        raise Problem(422, 'invalid_cursor') from error


def encode_insert_cursor(covered):
    payload = json.dumps(sorted(covered), separators=(',', ':')).encode('utf-8')
    token = base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')
    return _CURSOR_PREFIX + token


def next_insert_cursor(after, covered, records):
    if not records:
        # Preserve the caller's token exactly, including None for a first empty page.
        return after
    return encode_insert_cursor(covered | {record.seq for record in records})
