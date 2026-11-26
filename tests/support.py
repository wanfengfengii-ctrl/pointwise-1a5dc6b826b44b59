import json
import subprocess
import sys
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import HTTPHandler, ProxyHandler, Request, build_opener


def sample():
    path = Path(__file__).resolve().parents[1] / 'samples' / 'show.json'
    return json.loads(path.read_text(encoding='utf-8'))


class Client:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}'

    def request(self, operation, data, *, discard=False):
        opener = build_opener(ProxyHandler({}), HTTPHandler())
        request = Request(f'{self.base}/{operation}', data=json.dumps(data).encode('utf-8'),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            response = opener.open(request, timeout=12)
        except HTTPError as error:
            response = error
        with response:
            status = response.getcode()
            if discard and status == 200:
                return status, None
            return status, json.load(response)


class HTTPFixture:
    def __init__(self):
        self.process = None
        self.client = None

    def __enter__(self):
        self.directory = TemporaryDirectory(prefix='prompt-http-')
        self.database = Path(self.directory.name) / 'show.sqlite3'
        try:
            self.start()
        except BaseException:
            self.directory.cleanup()
            raise
        return self

    def __exit__(self, *exc):
        try:
            self.stop()
        finally:
            self.directory.cleanup()

    def start(self):
        process = subprocess.Popen([sys.executable, '-B', '-m', 'control.http',
                                    '--database', str(self.database), '--port', '0'],
                                   stdout=subprocess.PIPE, text=True)
        self.process = process
        lines = Queue(maxsize=1)
        reader = Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = lines.get(timeout=8)
            if not line:
                raise RuntimeError('HTTP service exited before announcing its port')
            self.client = Client(json.loads(line)['port'])
        except BaseException:
            self.stop()
            raise
        finally:
            reader.join(timeout=1)

    def stop(self):
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)
        finally:
            process.stdout.close()
            self.client = None

    def restart(self):
        self.stop()
        self.start()


class APITestCase(TestCase):
    def setUp(self):
        self.service = self.enterContext(HTTPFixture())

    def call(self, operation, status=200, *, discard=False, **data):
        actual, result = self.service.client.request(operation, data, discard=discard)
        self.assertEqual(actual, status, (operation, data, result))
        return result

    def issue(self, *, draft=None, request_id='I1'):
        draft = sample()['draft'] if draft is None else draft
        self.call('draft', **draft)
        return self.call('issue', draft_id=draft['draft_id'], request_id=request_id)

    def open(self, edition_id, *, show_id='S', required_cards=None, bindings=None, status=200):
        return self.call('open', status, show_id=show_id, edition_id=edition_id,
                         bindings={'K': 'G', 'L': 'H'} if bindings is None else bindings,
                         required_cards=[] if required_cards is None else required_cards)

    def manual(self, request_id, cards, status=200, *, show_id='S', discard=False):
        return self.call('send', status, show_id=show_id, request_id=request_id,
                         cards=cards, discard=discard)

    def key(self, request_id, key_id='K', status=200, *, show_id='S', discard=False):
        return self.call('key', status, show_id=show_id, request_id=request_id,
                         key_id=key_id, discard=discard)

    def inbox(self, seat='left', after=0, status=200, *, show_id='S'):
        return self.call('inbox', status, show_id=show_id, seat=seat, after=after)

    def close(self, request_id='CL', status=200, *, show_id='S'):
        return self.call('close', status, show_id=show_id, request_id=request_id)


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual,
             code_paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id, 'input': inputs, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream_actual,
        'code_paths': code_paths, 'oracle': oracle,
    }, ensure_ascii=False, separators=(',', ':')), flush=True)
