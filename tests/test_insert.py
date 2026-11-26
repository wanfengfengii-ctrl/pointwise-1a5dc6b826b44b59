from tests.support import APITestCase


class InsertCardTests(APITestCase):
    def open_insert(self, edition_id=None, *, show_id='INS', required_cards=None,
                    bindings=None, insert_mode=True, status=200):
        edition_id = edition_id or self.issue()['edition_id']
        return self.call(
            'open', status, show_id=show_id, edition_id=edition_id,
            bindings={'K': 'G', 'L': 'H'} if bindings is None else bindings,
            required_cards=['A', 'B'] if required_cards is None else required_cards,
            insert_mode=insert_mode,
        )

    def reserve(self, pack_id='P', cards=('A',), status=200, show_id='INS'):
        return self.call('insert_reserve', status, show_id=show_id,
                         pack_id=pack_id, cards=list(cards))

    def returned(self, played=('A',), pack_id='P', status=200, show_id='INS'):
        return self.call('insert_return', status, show_id=show_id,
                         pack_id=pack_id, played=list(played))

    def inbox(self, after=None, status=200, seat='left', show_id='INS'):
        return self.call('inbox', status, show_id=show_id, seat=seat, after=after)

    def test_open_mode_is_idempotent_configuration(self):
        edition_id = self.issue()['edition_id']
        self.open_insert(edition_id)
        self.open_insert(edition_id)
        self.call('open', 409, show_id='INS', edition_id=edition_id,
                  bindings={'K': 'G', 'L': 'H'}, required_cards=['A', 'B'])
        self.call('open', 409, show_id='INS', edition_id=edition_id,
                  bindings={'K': 'G', 'L': 'H'}, required_cards=['A', 'B'],
                  insert_mode=False)
        self.call('open', 422, show_id='BAD-MODE', edition_id=edition_id,
                  bindings={}, required_cards=[], insert_mode='yes')

    def test_reserve_freezes_reported_order_and_slots(self):
        edition_id = self.issue()['edition_id']
        self.open_insert(edition_id, required_cards=[])
        result = self.reserve(cards=['B', 'A'])
        self.assertEqual([(c['card_id'], c['seq'], c['position']) for c in result['cards']],
                         [('B', 1, 2), ('A', 2, 1)])
        self.assertEqual(result['edition_id'], edition_id)
        self.assertEqual(result['cards'][0]['source'], {
            'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'B'})

    def test_reserve_rejects_bad_parameters_and_conflicting_pack(self):
        self.open_insert(self.issue()['edition_id'], required_cards=[])
        for cards in ([], ['A'] * 5, ['A', 'A'], [1], ['X']):
            with self.subTest(cards=cards):
                self.reserve(cards=cards, status=422)
        self.call('insert_reserve', 422, show_id='INS', pack_id='BAD', cards='A')
        self.call('insert_reserve', 404, show_id='missing', pack_id='P', cards=['A'])
        self.reserve('P', ['A'])
        self.reserve('Q', ['B'], status=409)
        self.reserve('P', ['B'], status=409)
        self.assertEqual([c['card_id'] for c in self.reserve('P', ['A'])['cards']], ['A'])

    def test_normal_show_cannot_reserve(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id, show_id='NORMAL', required_cards=[])
        self.reserve(show_id='NORMAL', status=409)

    def test_network_candidates_skip_pending_pack(self):
        edition_id = self.issue()['edition_id']
        self.open_insert(edition_id, required_cards=[])
        self.reserve(cards=['A'])
        key = self.key('K1', show_id='INS')
        self.assertEqual((key['card_id'], key['seq']), ('B', 2))
        manual = self.manual('M1', ['A', 'C'], show_id='INS')
        self.assertEqual((manual['card_id'], manual['seq']), ('C', 3))

    def test_prefix_return_uses_fixed_slots_and_replays(self):
        edition_id = self.issue()['edition_id']
        self.open_insert(edition_id, required_cards=[])
        self.reserve(cards=['B', 'A'])
        self.returned(['A'], status=409)
        result = self.returned(['B'])
        self.assertEqual([(s['card_id'], s['seq']) for s in result['sends']], [('B', 1)])
        self.assertEqual(result['sends'][0]['origin'],
                         {'kind': 'offline', 'pack_id': 'P'})
        self.assertNotIn('request_id', result['sends'][0])
        self.assertEqual(self.returned(['B']), result)
        self.returned(['B', 'A'], status=409)
        self.call('insert_return', 409, show_id='INS', pack_id='MISSING', played=[])
        self.call('insert_return', 422, show_id='INS', pack_id='P', played='B')

    def test_opaque_cursor_covers_delivered_items_not_late_slots(self):
        self.open_insert(self.issue()['edition_id'], required_cards=[])
        self.reserve(cards=['A'])
        b = self.key('K1', show_id='INS')
        first = self.inbox()
        self.assertEqual(first['items'], [b])
        cursor = first['next_cursor']
        self.assertIsInstance(cursor, str)
        self.assertEqual(self.inbox(after=0), first)
        self.inbox(after=-1, status=422)
        self.inbox(after=True, status=422)
        self.inbox(after='not-a-cursor', status=422)

        a = self.returned(['A'])['sends'][0]
        continued = self.inbox(after=cursor)
        self.assertEqual(continued['items'], [a])
        stable = self.inbox(after=continued['next_cursor'])
        self.assertEqual(stable['items'], [])
        self.assertEqual(stable['next_cursor'], continued['next_cursor'])
        self.assertEqual([x['card_id'] for x in self.inbox()['items']], ['A', 'B'])

    def test_empty_prefix_leaves_hole_and_next_slot_continues(self):
        self.open_insert(self.issue()['edition_id'])
        self.reserve(cards=['A'])
        b = self.call('send', 200, show_id='INS', request_id='M1', group='G')
        self.assertEqual((b['card_id'], b['seq']), ('B', 2))
        cursor = self.inbox()['next_cursor']
        self.assertEqual(self.returned([])['sends'], [])
        empty = self.inbox(after=cursor)
        self.assertEqual(empty['items'], [])
        self.assertEqual(empty['next_cursor'], cursor)
        a = self.key('K2', show_id='INS')
        self.assertEqual((a['card_id'], a['seq']), ('A', 3))
        page = self.inbox(after=cursor)
        self.assertEqual(page['items'], [a])
        archive = self.close(show_id='INS')
        self.assertEqual([(s['card_id'], s['seq']) for s in archive['sends']],
                         [('B', 2), ('A', 3)])

    def test_pending_pack_blocks_close_then_archive_survives_restart(self):
        edition_id = self.issue()['edition_id']
        self.open_insert(edition_id)
        self.reserve(cards=['A'])
        self.key('K1', show_id='INS')
        self.close(status=409, show_id='INS')
        returned = self.returned(['A'])
        archive = self.close(show_id='INS')
        self.assertEqual([s['card_id'] for s in archive['sends']], ['A', 'B'])
        self.service.restart()
        self.assertEqual(self.call('archive_read', show_id='INS'), archive)
        self.assertEqual(self.returned(['A']), returned)
        self.reserve(cards=['A'])
        self.call('insert_reserve', 409, show_id='INS', pack_id='Q', cards=['B'])
        self.key('K2', status=409, show_id='INS')

    def test_first_empty_insert_page_keeps_null_cursor(self):
        self.open_insert(self.issue()['edition_id'], required_cards=[])
        page = self.inbox()
        self.assertEqual(page['items'], [])
        self.assertIsNone(page['next_cursor'])
        self.reserve(cards=['A'])
        self.returned(['A'])
        page = self.inbox()
        self.assertEqual([x['card_id'] for x in page['items']], ['A'])
