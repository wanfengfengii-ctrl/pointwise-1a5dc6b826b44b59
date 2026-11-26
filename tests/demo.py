from tests.support import HTTPFixture, sample, scenario


def expect(actual, expected):
    if actual != expected:
        raise AssertionError(f'expected {expected!r}, got {actual!r}')


def main():
    data = sample()
    with HTTPFixture() as service:
        def call(operation, payload, expected_status=200):
            status, result = service.client.request(operation, payload)
            expect(status, expected_status)
            return result

        draft = data['draft']
        expect(call('draft', draft), {'draft_id': 'D', 'order': ['A', 'B', 'C']})
        bad_draft = {**draft, 'groups': {**draft['groups'], 'G': ['A', 'X']}}
        expect(call('draft', bad_draft, 422)['error'], 'unknown_group_card')
        edition = call('issue', data['issue'])
        edition_id = edition['edition_id']
        expect(edition['groups']['G'], ['B', 'A'])
        revised = {**draft, 'cards': [{**draft['cards'][0], 'text': '改稿后收桌'}, *draft['cards'][1:]]}
        call('draft', revised)
        fresh = call('issue', {**data['issue'], 'request_id': 'I2'})
        if fresh['edition_id'] == edition_id:
            raise AssertionError('a new issue reused the old edition identity')
        expect(fresh['cards'][0]['text'], '改稿后收桌')
        expect(call('issue', {'edition_id': edition_id}), edition)
        opened = call('open', {**data['open'], 'edition_id': edition_id})
        expect(opened, {'show_id': 'S', 'edition_id': edition_id, 'state': 'running'})
        a = call('key', data['key'])
        expect(call('close', data['close'], 409)['missing_cards'], ['C'])
        c, b = [call('send', request) for request in data['manual']]
        sends = [a, c, b]
        expected = [
            ['A', 1, 1, 'left', '左幕收桌', {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'A'}],
            ['C', 2, 3, 'right', '右幕灯转暖', {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'C'}],
            ['B', 3, 2, 'left', '左幕备桌', {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'B'}],
        ]
        actual = [[row[field] for field in ('card_id', 'seq', 'position', 'seat', 'text', 'source')]
                  for row in sends]
        expect(actual, expected)
        left, right = [call('inbox', request) for request in data['inboxes']]
        expect((left['items'], left['next_cursor']), ([a, b], 3))
        expect((right['items'], right['next_cursor']), ([c], 2))
        archive = call('close', data['close'])
        expect(archive['sends'], sends)
        expect(archive['edition_id'], edition_id)
        service.restart()
        by_show = call('archive_read', {'show_id': 'S'})
        by_archive = call('archive_read', {'archive_id': archive['archive_id']})
        expect(by_show, archive)
        expect(by_archive, archive)
        expect(call('close', data['close']), archive)
        downstream = {'left': [row['seq'] for row in left['items']], 'left_cursor': left['next_cursor'],
                      'right': [row['seq'] for row in right['items']], 'right_cursor': right['next_cursor'],
                      'archive': [row['card_id'] for row in by_show['sends']], 'edition': by_show['edition_id']}
        downstream_expected = {'left': [1, 3], 'left_cursor': 3, 'right': [2], 'right_cursor': 2,
                               'archive': ['A', 'C', 'B'], 'edition': edition_id}
        expect(downstream, downstream_expected)
        scenario('normal_send', data, expected, actual, downstream_expected, downstream,
                 ['editions/issue.py', 'control/keys.py', 'dispatch/selection.py', 'dispatch/ledger.py',
                  'readback/inbox.py', 'readback/reconciliation.py', 'readback/archive.py'],
                 '按固定卡序手算 G 先给 A，H 给 C，再从 G 取 B。按席分出位置 1、3 和 2，场报保留同一发行及三条实发。')


if __name__ == '__main__':
    main()
