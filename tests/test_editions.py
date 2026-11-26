from tests.support import APITestCase, sample


class EditionTests(APITestCase):
    def test_issue_fixed(self):
        old = self.issue()
        changed = sample()['draft']
        changed['cards'][0]['text'] = '左幕移椅'
        changed['order'] = ['B', 'A', 'C']
        self.call('draft', **changed)
        actual = self.call('issue', edition_id=old['edition_id'])
        self.assertEqual(actual, old)
        self.assertEqual(actual['order'], ['A', 'B', 'C'])
        self.assertEqual(actual['cards'][0], {
            'card_id': 'A', 'text': '左幕收桌', 'seat': 'left', 'position': 1,
            'source': {'draft_id': 'D', 'edition_id': old['edition_id'], 'card_id': 'A'},
        })
        self.assertEqual(actual['groups']['G'], ['B', 'A'])
        new = self.call('issue', draft_id='D', request_id='I2')
        self.assertNotEqual(new['edition_id'], old['edition_id'])
        self.assertEqual(new['order'], ['B', 'A', 'C'])
        self.assertEqual(new['cards'][1]['text'], '左幕移椅')
        self.assertEqual(new['cards'][1]['position'], 2)
        self.assertEqual(new['cards'][1]['source'], {
            'draft_id': 'D', 'edition_id': new['edition_id'], 'card_id': 'A',
        })
        self.assertEqual(self.call('issue', draft_id='D', request_id='I1'), old)
        self.assertEqual(self.call('issue', draft_id='D', request_id='I2'), new)

    def test_unknown_card(self):
        bad = sample()['draft']
        bad['groups']['G'] = ['A', 'X']
        self.assertEqual(self.call('draft', 422, **bad)['error'], 'unknown_group_card')
        self.call('issue', 404, draft_id='D', request_id='I1')
        old = self.issue()
        self.call('draft', 422, **bad)
        fresh = self.call('issue', draft_id='D', request_id='I2')
        self.assertEqual(fresh['groups'], old['groups'])
        self.assertEqual(fresh['order'], ['A', 'B', 'C'])

    def test_reject_invalid_draft(self):
        self.call('draft', **sample()['draft'])
        for defect in ('duplicate_card', 'blank_text', 'blank_seat', 'empty_group',
                       'duplicate_member', 'missing_order_card', 'repeated_order_card',
                       'unknown_order_card'):
            with self.subTest(defect=defect):
                draft = sample()['draft']
                if defect == 'duplicate_card':
                    draft['cards'].append(draft['cards'][0].copy())
                elif defect == 'blank_text':
                    draft['cards'][0]['text'] = ' '
                elif defect == 'blank_seat':
                    draft['cards'][0]['seat'] = ''
                elif defect == 'empty_group':
                    draft['groups']['G'] = []
                elif defect == 'duplicate_member':
                    draft['groups']['G'] = ['A', 'A']
                elif defect == 'missing_order_card':
                    draft['order'] = ['A', 'B']
                elif defect == 'repeated_order_card':
                    draft['order'] = ['A', 'A', 'C']
                else:
                    draft['order'] = ['A', 'B', 'X']
                self.call('draft', 422, **draft)
        result = self.call('issue', draft_id='D', request_id='I1')
        self.assertEqual(result['order'], ['A', 'B', 'C'])
        self.assertEqual(result['cards'][0]['text'], '左幕收桌')
        self.assertEqual(result['groups']['G'], ['B', 'A'])

    def test_issue_request_conflict_and_missing_draft(self):
        self.call('issue', 404, draft_id='D', request_id='I1')
        issued = self.issue()
        other = sample()['draft']
        other['draft_id'] = 'other'
        self.call('draft', **other)
        self.call('issue', 409, draft_id='other', request_id='I1')
        self.assertEqual(self.call('issue', draft_id='D', request_id='I1'), issued)
        self.assertEqual(self.call('issue', draft_id='other', request_id='I2')['draft_id'], 'other')
        self.call('issue', 404, edition_id='absent')

    def test_init_preserves_draft(self):
        old = self.issue()
        changed = sample()['draft']
        changed['cards'][0]['text'] = '保留走台后改词'
        self.call('draft', **changed)
        self.service.restart()
        self.assertEqual(self.call('issue', draft_id='D', request_id='I1'), old)
        new = self.call('issue', draft_id='D', request_id='I2')
        self.assertEqual(new['cards'][0]['text'], '保留走台后改词')
