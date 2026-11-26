from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread

from control.http import PromptRequestHandler, make_server
from tests.support import APITestCase, Client, sample


class ArchiveTests(APITestCase):
    def test_early_close(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id, required_cards=['A', 'C'])
        first = self.key('K1')
        self.assertEqual(self.close(status=409), {'error': 'required_cards_missing', 'missing_cards': ['C']})
        self.call('archive_read', 404, show_id='S')
        next_send = self.key('K2', 'L')
        archive = self.close()
        self.assertEqual(archive['edition_id'], edition_id)
        self.assertEqual(archive['sends'], [first, next_send])
        self.assertEqual(self.close(), archive)

    def test_required_identity(self):
        self.open(self.issue()['edition_id'], required_cards=['A', 'C'])
        b = self.manual('M1', ['B'])
        c = self.manual('M2', ['C'])
        error = self.close(status=409)
        self.assertEqual(error['missing_cards'], ['A'])
        self.call('archive_read', 404, show_id='S')
        a = self.manual('M3', ['A'])
        archive = self.close()
        self.assertEqual(archive['sends'], [b, c, a])
        self.assertEqual([row['seq'] for row in archive['sends']], [1, 2, 3])

    def test_archive_fixed(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id, required_cards=['A'])
        first = self.key('K1')
        archive = self.close()
        changed = sample()['draft']
        changed['cards'][0]['text'] = '新版换景'
        new_id = self.issue(draft=changed, request_id='I2')['edition_id']
        self.open(new_id, show_id='S2', required_cards=['A'])
        second = self.key('K1', show_id='S2')
        newer = self.close('CL2', show_id='S2')
        self.assertNotEqual(newer['archive_id'], archive['archive_id'])
        self.service.restart()
        self.assertEqual(self.call('archive_read', show_id='S'), archive)
        self.assertEqual(self.call('archive_read', archive_id=archive['archive_id']), archive)
        self.assertEqual(self.call('archive_read', show_id='S2'), newer)
        self.assertEqual(self.call('archive_read', archive_id=newer['archive_id']), newer)
        self.assertEqual(archive['sends'], [first])
        self.assertEqual(first['text'], '左幕收桌')
        self.assertEqual(first['source'], {'edition_id': edition_id, 'draft_id': 'D', 'card_id': 'A'})
        self.assertEqual(newer['edition_id'], new_id)
        self.assertEqual(newer['sends'], [second])
        self.assertEqual(second['text'], '新版换景')
        self.assertEqual(self.close(), archive)
        self.assertEqual(self.close('alias'), archive)
        self.close('alias', 409, show_id='S2')
        self.close('CL', 409, show_id='S2')
        self.call('archive_read', 404, show_id='missing')
        self.call('archive_read', 404, archive_id='missing')
        self.call('archive_read', 422, show_id='S', archive_id=archive['archive_id'])

    def test_close_send_serialization(self):
        edition_id = self.issue()['edition_id']
        self.open(edition_id, required_cards=['A'])
        first = self.manual('M1', ['A'])
        self.open(edition_id, show_id='send-first', required_cards=['A'])
        a = self.manual('M1', ['A'], show_id='send-first')
        b = self.manual('M2', ['B'], show_id='send-first')
        self.assertEqual(self.close('other-close', show_id='send-first')['sends'], [a, b])
        self.service.stop()

        sealing, release, sending = Event(), Event(), Event()

        class ObservedHandler(PromptRequestHandler):
            def open_database(self):
                db = super().open_database()
                def observe(sql):
                    statement = sql.strip().upper()
                    if self.path == '/close' and statement.startswith('UPDATE SHOWS'):
                        sealing.set()
                        release.wait(timeout=20)
                    if self.path == '/send' and statement == 'BEGIN IMMEDIATE':
                        sending.set()
                db.set_trace_callback(observe)
                return db

        with make_server(self.service.database, handler_class=ObservedHandler) as server:
            thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
            thread.start()
            client = Client(server.server_port)
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    close = executor.submit(client.request, 'close', {'show_id': 'S', 'request_id': 'CL'})
                    try:
                        self.assertTrue(sealing.wait(timeout=5), 'close did not reach the seal update')
                        late = executor.submit(client.request, 'send',
                                               {'show_id': 'S', 'request_id': 'M2', 'cards': ['B']})
                        self.assertTrue(sending.wait(timeout=5), 'send did not reach the writer boundary')
                        status, result = client.request('archive_read', {'show_id': 'S'})
                        self.assertEqual((status, result['error']), (404, 'archive_not_found'))
                    finally:
                        release.set()
                    status, archive = close.result(timeout=12)
                    self.assertEqual(status, 200)
                    self.assertEqual(archive['sends'], [first])
                    status, result = late.result(timeout=12)
                    self.assertEqual((status, result['error']), (409, 'show_closed'))
                    self.assertEqual(client.request('archive_read', {'show_id': 'S'}), (200, archive))
                    status, inbox = client.request('inbox', {'show_id': 'S', 'seat': 'left', 'after': 0})
                    self.assertEqual((status, inbox['items']), (200, [first]))
            finally:
                release.set()
                server.shutdown()
                thread.join(timeout=5)
