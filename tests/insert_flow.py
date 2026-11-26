"""Real HTTP checks for the offline rehearsal insert-pack flow."""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.support import HTTPFixture

ROOT = _ROOT


def insert_sample():
    return json.loads((ROOT / 'samples' / 'insert_cards.json').read_text(encoding='utf-8'))


def _call(service, operation, payload, expected_status=200):
    status, result = service.client.request(operation, payload)
    if status != expected_status:
        raise AssertionError(
            f'{operation}: expected HTTP {expected_status}, got {status}: {result!r}')
    return result


def _draft_and_edition(service, data):
    draft_path = ROOT / data.get('draft_file', 'samples/show.json')
    draft = json.loads(draft_path.read_text(encoding='utf-8'))['draft']
    _call(service, 'draft', draft)
    edition = _call(service, 'issue', data['issue'])
    return edition['edition_id']


def _ids(items):
    return [(item['card_id'], item['seq']) for item in items]


def verify_prefix_and_archive(service=None, *, verbose=False):
    """Read B first, return prefix A through an old cursor, close and reopen."""
    own_fixture = service is None
    service = service or HTTPFixture()
    if own_fixture:
        service.__enter__()
    try:
        data = insert_sample()
        edition_id = _draft_and_edition(service, data)
        open_request = {**data['open'], 'edition_id': edition_id}
        _call(service, 'open', open_request)

        reserve = _call(service, 'insert_reserve', data['reserve'])
        assert _ids(reserve['cards']) == [('A', 1)]
        b_send = _call(service, 'key', data['key'])
        assert (b_send['card_id'], b_send['seq']) == ('B', 2)

        first_page = _call(service, 'inbox', data['first_read'])
        assert _ids(first_page['items']) == [('B', 2)]
        b_cursor = first_page['next_cursor']
        assert isinstance(b_cursor, str) and b_cursor

        _call(service, 'close', data['close'], 409)

        returned = _call(service, 'insert_return', data['return_played'])
        expected_a = {
            'show_id': data['return_played']['show_id'], 'seq': 1, 'card_id': 'A',
            'text': '左幕收桌', 'seat': 'left', 'position': 1,
            'source': {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'A'},
            'origin': {'kind': 'offline', 'pack_id': 'P'},
        }
        assert returned == {
            'show_id': data['return_played']['show_id'], 'pack_id': 'P',
            'sends': [expected_a],
        }

        continued = _call(service, 'inbox',
                          {**data['first_read'], 'after': b_cursor})
        assert continued['items'] == [expected_a]
        full_cursor = continued['next_cursor']
        assert full_cursor != b_cursor

        empty_page = _call(service, 'inbox',
                           {**data['first_read'], 'after': full_cursor})
        assert empty_page == {
            'show_id': data['first_read']['show_id'], 'seat': 'left',
            'items': [], 'next_cursor': full_cursor,
        }

        fresh_page = _call(service, 'inbox', data['first_read'])
        assert _ids(fresh_page['items']) == [('A', 1), ('B', 2)]
        fresh_empty = _call(service, 'inbox',
                            {**data['first_read'], 'after': fresh_page['next_cursor']})
        assert fresh_empty['items'] == []

        archive = _call(service, 'close', data['close'])
        assert _ids(archive['sends']) == [('A', 1), ('B', 2)]
        assert 'request_id' not in archive['sends'][0]
        assert archive['sends'][0] == expected_a

        service.restart()
        reopened = _call(service, 'archive_read', data['archive_read'])
        assert reopened == archive
        assert _call(service, 'close', data['close']) == archive
        assert _call(service, 'insert_return', data['return_played']) == returned
        _call(service, 'insert_return', data['return_empty'], 409)

        old_cursor_page = _call(service, 'inbox',
                                {**data['first_read'], 'after': b_cursor})
        assert old_cursor_page['items'] == [expected_a]

        if verbose:
            print(json.dumps({
                'insert_demo': 'read_before_return',
                'first_read': _ids(first_page['items']),
                'after_return_with_old_cursor': _ids(continued['items']),
                'archive_after_reopen': _ids(reopened['sends']),
            }, ensure_ascii=False, sort_keys=True))
        return archive
    finally:
        if own_fixture:
            service.__exit__(None, None, None)


def verify_empty_prefix_releases_card_but_keeps_slot():
    data = insert_sample()
    with HTTPFixture() as service:
        edition_id = _draft_and_edition(service, data)
        show_id = 'S-empty-prefix'
        _call(service, 'open', {
            **data['open'], 'show_id': show_id, 'edition_id': edition_id,
        })
        _call(service, 'insert_reserve', {
            **data['reserve'], 'show_id': show_id,
        })
        b_send = _call(service, 'send', {
            **data['manual'], 'show_id': show_id,
        })
        assert (b_send['card_id'], b_send['seq']) == ('B', 2)

        read_request = {**data['first_read'], 'show_id': show_id}
        first_page = _call(service, 'inbox', read_request)
        b_cursor = first_page['next_cursor']

        returned = _call(service, 'insert_return', {
            **data['return_empty'], 'show_id': show_id,
        })
        assert returned['sends'] == []
        empty_page = _call(service, 'inbox',
                           {**read_request, 'after': b_cursor})
        assert empty_page == {
            'show_id': show_id, 'seat': 'left', 'items': [],
            'next_cursor': b_cursor,
        }

        a_send = _call(service, 'key', {**data['key'], 'show_id': show_id})
        assert (a_send['card_id'], a_send['seq']) == ('A', 3)
        continued = _call(service, 'inbox',
                          {**read_request, 'after': b_cursor})
        assert _ids(continued['items']) == [('A', 3)]

        archive = _call(service, 'close', {
            **data['close'], 'show_id': show_id,
            'request_id': 'CL-empty-prefix',
        })
        assert _ids(archive['sends']) == [('B', 2), ('A', 3)]
        service.restart()
        assert _call(service, 'archive_read',
                     {'show_id': show_id}) == archive


def verify_all():
    verify_prefix_and_archive(verbose=True)
    verify_empty_prefix_releases_card_but_keeps_slot()
    print('INSERT FLOW VERIFY PASS')


def demonstrate():
    print('插段演示：先读联网 B@2，核回离线前缀 A@1，再用原游标补领 A。')
    archive = verify_prefix_and_archive(verbose=True)
    print('重开服务后 archive_read 得到同一结场件：'
          + json.dumps([(item['card_id'], item['seq']) for item in archive['sends']],
                       ensure_ascii=False))


if __name__ == '__main__':
    verify_all()
