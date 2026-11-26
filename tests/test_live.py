from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from tests.support import APITestCase, sample, scenario


class LiveTests(APITestCase):
    def test_key_and_manual_send(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id, required_cards=['A', 'B'])
        first = self.key('K1')
        second = self.call('send', show_id='S', request_id='M1', group='G')
        projected = [[r['card_id'], r['seq'], r['seat'], r['source']] for r in (first, second)]
        expected = [[card_id, seq, 'left', {'edition_id': edition_id, 'draft_id': 'D', 'card_id': card_id}]
                    for card_id, seq in (('A', 1), ('B', 2))]
        self.assertEqual(projected, expected)
        self.assertEqual(first['origin'], {'kind': 'key', 'key_id': 'K'})
        self.assertEqual(second['origin'], {'kind': 'manual'})
        self.assertEqual([first['text'], second['text']], ['左幕收桌', '左幕备桌'])
        inbox = self.inbox()
        self.assertEqual(inbox['items'], [first, second])
        self.assertEqual(inbox['next_cursor'], 2)
        self.assertEqual(self.inbox('right')['items'], [])
        archive = self.close()
        self.assertEqual(archive['sends'], [first, second])
        downstream = {'seat': [row['card_id'] for row in inbox['items']],
                      'cursor': inbox['next_cursor'],
                      'archive': [row['card_id'] for row in archive['sends']]}
        expected_downstream = {'seat': ['A', 'B'], 'cursor': 2, 'archive': ['A', 'B']}
        self.assertEqual(downstream, expected_downstream)
        scenario('normal_send', {'order': ['A', 'B', 'C'], 'G': ['B', 'A'],
                                'requests': ['key K', 'manual G']}, expected, projected,
                 expected_downstream, downstream,
                 ['control/keys.py', 'editions/order.py', 'dispatch/selection.py',
                  'dispatch/ledger.py', 'readback/inbox.py', 'readback/close.py'],
                 '从发行序手算先 A 后 B，左幕取到两个位置，实发摘要也为 A、B。')

    def test_open_snapshot(self):
        edition_id = self.issue()['edition_id']
        opened = self.open(edition_id, required_cards=['A', 'C'])
        changed = sample()['draft']
        changed['cards'][0]['text'] = '新版左幕'
        changed['order'] = ['B', 'A', 'C']
        new = self.issue(draft=changed, request_id='I2')
        self.assertEqual(self.open(edition_id, required_cards=['C', 'A']), opened)
        self.open(new['edition_id'], required_cards=['A', 'C'], status=409)
        first = self.key('K1')
        self.assertEqual((first['card_id'], first['text']), ('A', '左幕收桌'))
        self.assertEqual(first['source']['edition_id'], edition_id)
        self.assertEqual(self.inbox()['items'], [first])

    def test_open_rejections_and_conflict(self):
        edition_id = self.issue()['edition_id']
        new = self.call('issue', draft_id='D', request_id='I2')['edition_id']
        self.open('missing', status=404)
        self.open(edition_id, required_cards=['X'], status=422)
        self.open(edition_id, required_cards=[{'edition_id': new, 'card_id': 'A'}], status=422)
        self.open(edition_id, bindings={'K': 'missing'}, status=422)
        self.open(edition_id, bindings={'K': {'edition_id': new, 'group_id': 'G'}}, status=422)
        self.inbox(status=404)
        self.open(edition_id, required_cards=['A'])
        self.open(edition_id, required_cards=['C'], status=409)
        self.open(edition_id, required_cards=['A'], bindings={'K': 'H', 'L': 'G'}, status=409)
        self.assertEqual(self.key('R')['card_id'], 'A')

    def test_key_binding(self):
        draft = sample()['draft']
        draft['groups']['G'] = ['A']
        edition_id = self.issue(draft=draft)['edition_id']
        self.open(edition_id)
        self.key('R', 'unbound', 422)
        right = self.key('R', 'L')
        left = self.key('Q', 'K')
        self.assertEqual([(row['card_id'], row['seq']) for row in (right, left)], [('C', 1), ('A', 2)])
        self.assertEqual(self.inbox('right')['items'], [right])
        self.assertEqual(self.inbox('left')['items'], [left])

    def test_ordered_candidates_and_no_card(self):
        self.open(self.issue()['edition_id'])
        self.call('send', 422, show_id='S', request_id='invalid')
        self.call('send', 422, show_id='S', request_id='invalid', group='G', cards=['A'])
        self.manual('invalid', [], 422)
        first = self.manual('r1', ['B', 'A'])
        second = self.manual('r2', ['B', 'A'])
        self.assertEqual([(r['card_id'], r['seq']) for r in (first, second)], [('A', 1), ('B', 2)])
        self.manual('r3', ['B', 'A'], 409)
        self.key('r3', 'K', 409)
        self.assertEqual(self.key('r3', 'L')['seq'], 3)
        self.assertEqual(self.inbox()['items'], [first, second])

    def test_foreign_card(self):
        edition_id = self.issue()['edition_id']
        other = self.call('issue', draft_id='D', request_id='I2')['edition_id']
        self.open(edition_id)
        self.manual('bad', ['X'], 422)
        self.manual('bad', ['B', {'edition_id': other, 'card_id': 'A'}], 422)
        self.call('send', 422, show_id='S', request_id='bad',
                  group={'edition_id': other, 'group_id': 'G'})
        self.assertEqual(self.inbox()['items'], [])
        good = self.manual('bad', [{'edition_id': edition_id, 'card_id': 'A'}])
        self.assertEqual((good['card_id'], good['seq']), ('A', 1))
        self.assertEqual(good['source']['edition_id'], edition_id)
        self.assertEqual(self.inbox()['items'], [good])

    def test_conflicting_request(self):
        self.open(self.issue()['edition_id'])
        first = self.manual('M', ['B', 'A'])
        self.manual('M', ['B'], 409)
        self.manual('M', ['A', 'B'], 409)
        self.key('M', 'K', 409)
        self.assertEqual(self.manual('M', ['B', 'A']), first)
        right = self.key('K1', 'L')
        self.key('K1', 'K', 409)
        self.key('K1', 'unknown', 409)
        self.manual('K1', ['C'], 409)
        self.assertEqual(self.key('K1', 'L'), right)
        self.assertEqual(self.manual('M2', ['B'])['seq'], 3)

    def test_receipt_reopen(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id)
        self.assertIsNone(self.manual('M', ['B', 'A'], discard=True))
        self.service.restart()
        actual = self.manual('M', ['B', 'A'])
        self.assertEqual((actual['card_id'], actual['seq'], actual['seat']), ('A', 1, 'left'))
        self.assertEqual(actual['source'], {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'A'})
        self.assertEqual(self.inbox()['items'], [actual])
        self.assertEqual(self.manual('new', ['B'])['seq'], 2)

    def test_key_replay(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id)
        self.assertIsNone(self.key('K1', discard=True))
        self.service.restart()
        actual = self.key('K1')
        self.assertEqual((actual['card_id'], actual['seq'], actual['seat']), ('A', 1, 'left'))
        self.assertEqual(actual['origin'], {'kind': 'key', 'key_id': 'K'})
        self.assertEqual(actual['source']['edition_id'], edition_id)
        self.assertEqual(self.inbox()['items'], [actual])
        self.assertEqual(self.key('K2')['card_id'], 'B')

    def test_seat_cursor_and_unknown_inbox(self):
        draft = sample()['draft']
        draft['cards'].append({'card_id': 'D', 'text': '右幕收灯', 'seat': 'right'})
        draft['order'].append('D')
        self.open(self.issue(draft=draft)['edition_id'])
        self.inbox('unknown', status=404)
        self.inbox(show_id='unknown', status=404)
        self.inbox(after=-1, status=422)
        self.inbox(after=True, status=422)
        c = self.manual('r1', ['C'])
        a = self.manual('r2', ['A'])
        page = self.inbox()
        self.assertEqual((page['items'], page['next_cursor']), ([a], 2))
        d = self.manual('r3', ['D'])
        b = self.manual('r4', ['B'])
        page = self.inbox(after=page['next_cursor'])
        self.assertEqual((page['items'], page['next_cursor']), ([b], 4))
        self.assertEqual(self.inbox(after=2), page)
        self.assertEqual(self.inbox(after=4), {'show_id': 'S', 'seat': 'left', 'items': [], 'next_cursor': 4})
        self.assertEqual(self.inbox('right')['items'], [c, d])
        self.assertEqual(self.inbox(after=1 << 70)['next_cursor'], 1 << 70)

    def test_concurrent_send(self):
        self.open(self.issue()['edition_id'])
        gate = Barrier(2)
        def request(request_id):
            gate.wait(timeout=5)
            return self.service.client.request('send', {'show_id': 'S', 'request_id': request_id,
                                                        'cards': ['A']})
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(request, name) for name in ('M1', 'M2')]
            replies = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(status for status, _ in replies), [200, 409])
        winner = next(result for status, result in replies if status == 200)
        self.assertEqual((winner['card_id'], winner['seq']), ('A', 1))
        self.assertEqual(self.inbox()['items'], [winner])
        self.assertEqual(self.manual('M3', ['B'])['seq'], 2)

    def test_closed_send(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id)
        first = self.key('K1', 'L')
        second = self.manual('M1', ['A'])
        self.assertEqual(self.close()['sends'], [first, second])
        self.key('K1', 'L', 409)
        self.key('K2', 'K', 409)
        self.manual('M2', ['B'], 409)
        self.manual('M1', ['B'], 409)
        self.assertEqual(self.manual('M1', ['A']), second)
        self.open(edition_id, status=409)
        self.assertEqual(self.inbox()['items'], [second])
