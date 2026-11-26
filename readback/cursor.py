from contracts import Problem


def parse_cursor(value):
    if type(value) is not int or value < 0:
        raise Problem(422, 'invalid_cursor')
    return value


def next_cursor(after, records):
    return records[-1].seq if records else after
