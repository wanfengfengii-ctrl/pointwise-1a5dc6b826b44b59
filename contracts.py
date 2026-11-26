class Problem(Exception):
    def __init__(self, status, code, **details):
        super().__init__(code)
        self.status = status
        self.code = code
        self.details = details

    def as_payload(self):
        return {'error': self.code, **self.details}


def text_value(value, field):
    if not isinstance(value, str) or not value.strip():
        raise Problem(422, 'invalid_text', field=field)
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise Problem(422, 'invalid_text', field=field) from error
    return value


def require_fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise Problem(422, 'expected_object')
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise Problem(422, 'invalid_fields', missing=sorted(missing), extra=sorted(extra))
