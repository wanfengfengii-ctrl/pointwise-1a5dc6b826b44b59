import argparse
import json
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from contracts import Problem, require_fields, text_value
from control.bindings import BINDING_SCHEMA
from control.insert import insert_reserve, insert_return
from control.keys import send_key
from control.requests import KEY_REQUEST_SCHEMA
from control.show import SHOW_OPTION_SCHEMA, SHOW_SCHEMA, open_show
from control.store import connect_database, initialize_database, read_transaction, write_transaction
from dispatch.ledger import SEND_LEDGER_SCHEMA, migrate_ledger
from dispatch.packs import PACK_SCHEMA
from dispatch.receipts import SEND_RECEIPT_SCHEMA
from dispatch.send import send_manual
from editions.issue import EDITION_SCHEMA, issue_edition
from editions.lookup import get_edition
from editions.requests import ISSUE_REQUEST_SCHEMA
from readback.archive import ARCHIVE_SCHEMA, get_archive_by_number, get_archive_by_show
from readback.close import CLOSE_REQUEST_SCHEMA, close_show
from readback.inbox import read_inbox
from scripts.drafts import DRAFT_SCHEMA, put_draft

_SCHEMAS = (DRAFT_SCHEMA, EDITION_SCHEMA, ISSUE_REQUEST_SCHEMA, SHOW_SCHEMA,
            SHOW_OPTION_SCHEMA, BINDING_SCHEMA, SEND_LEDGER_SCHEMA, PACK_SCHEMA,
            SEND_RECEIPT_SCHEMA, KEY_REQUEST_SCHEMA, ARCHIVE_SCHEMA, CLOSE_REQUEST_SCHEMA)


def _read_edition(db, edition_id):
    return get_edition(db, edition_id).as_payload()


def _archive_read(db, show_id=None, archive_id=None):
    if (show_id is None) == (archive_id is None):
        raise Problem(422, 'expected_show_or_archive')
    if show_id is not None:
        record = get_archive_by_show(db, text_value(show_id, 'show_id'))
    else:
        record = get_archive_by_number(db, text_value(archive_id, 'archive_id'))
    if record is None:
        raise Problem(404, 'archive_not_found')
    return record.as_payload()


@dataclass(frozen=True)
class _Operation:
    action: Callable
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    writes: bool = True


_ROUTES = {
    '/draft': _Operation(put_draft, ('draft_id', 'cards', 'groups', 'order')),
    '/issue': _Operation(issue_edition, ('draft_id', 'request_id')),
    '/open': _Operation(open_show, ('show_id', 'edition_id', 'bindings', 'required_cards'),
                        ('insert_mode',)),
    '/insert_reserve': _Operation(insert_reserve, ('show_id', 'pack_id', 'cards')),
    '/insert_return': _Operation(insert_return, ('show_id', 'pack_id', 'played')),
    '/key': _Operation(send_key, ('show_id', 'key_id', 'request_id')),
    '/send': _Operation(send_manual, ('show_id', 'request_id'), ('group', 'cards')),
    '/inbox': _Operation(read_inbox, ('show_id', 'seat', 'after'), writes=False),
    '/close': _Operation(close_show, ('show_id', 'request_id')),
    '/archive_read': _Operation(_archive_read, (), ('show_id', 'archive_id'), writes=False),
}
_EDITION_READ = _Operation(_read_edition, ('edition_id',), writes=False)


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'invalid JSON constant {value}')


class PromptRequestHandler(BaseHTTPRequestHandler):
    def open_database(self):
        return connect_database(self.server.database)

    def _read_json(self):
        if self.headers.get_content_type() != 'application/json':
            raise Problem(400, 'expected_json')
        try:
            length = int(self.headers.get('Content-Length', ''))
            if length < 0:
                raise ValueError('negative content length')
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError('incomplete request body')
            return json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
        except (ValueError, OverflowError, RecursionError) as error:
            raise Problem(400, 'invalid_json') from error

    def _respond(self, status, payload):
        data = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def log_request(self, code='-', size='-'):
        if isinstance(code, int) and code >= 500:
            super().log_request(code, size)

    def do_POST(self):
        try:
            operation = _ROUTES.get(self.path)
            if operation is None:
                raise Problem(404, 'operation_not_found')
            data = self._read_json()
            if self.path == '/issue' and isinstance(data, dict) and 'edition_id' in data:
                operation = _EDITION_READ
            require_fields(data, operation.required, operation.optional)
            if self.path == '/archive_read' and len(data) != 1:
                raise Problem(422, 'expected_show_or_archive')
            transaction = write_transaction if operation.writes else read_transaction
            with closing(self.open_database()) as db, transaction(db):
                result = operation.action(db, **data)
        except Problem as error:
            self._respond(error.status, error.as_payload())
        else:
            self._respond(200, result)


class _PromptServer(ThreadingHTTPServer):
    def __init__(self, database, port, handler_class):
        self.database = database
        super().__init__(('127.0.0.1', port), handler_class)


def make_server(database, port=0, handler_class=PromptRequestHandler):
    initialize_database(database, _SCHEMAS)
    with closing(connect_database(database)) as db:
        migrate_ledger(db)
    return _PromptServer(database, port, handler_class)


def run_server(database, port=0):
    with make_server(database, port) as server:
        print(json.dumps({'port': server.server_port}), flush=True)
        server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description='槐巷剧场提词服务')
    parser.add_argument('--database', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args(argv)
    try:
        run_server(args.database, args.port)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
