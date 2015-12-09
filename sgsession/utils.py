from datetime import datetime
import re
import itertools
import logging

log = logging.getLogger(__name__)


def expand_braces(pattern):
    res = []
    parts = re.split(r'\{(.+?)\}', pattern)
    if len(parts) == 1:
        return parts
    specs = [x.split(',') for x in parts[1::2]]
    for product in itertools.product(*specs):
        parts[1::2] = product
        res.append(''.join(parts))
    return res


_isotime_re = re.compile(r'''
    ^
    (\d{4}) # year
    \D?
    (0[1-9]|1[0-2]) # month: 01 to 12
    \D?
    (0[1-9]|[12]\d|3[01]) # day
    \D? # a "T" or space
    (0[1-9]|1[0-2]) # hour
    \D?
    (0[1-9]|[1-5]\d) # minute
    \D?
    (0[1-9]|[1-5]\d|6[01]) # second (with leap, FFS)
    (?:\.(\d{1,6}))? # microsecond
    \D? # a "Z" or space
    (?:\d{3})? # timezone (which is ignored)
    $
''', re.VERBOSE)


def expect_datetime(timestamp, log_message=None, entity=None, **log_context):

    if not isinstance(timestamp, basestring):
        return timestamp

    msg = 'string timestamp (%r) found' % timestamp

    if entity:
        if 'type' in entity and 'id' in entity:
            msg = '%s in %s %s' % (msg, entity['type'], entity['id'])
        else:
            msg = '%s in %r' % (msg, entity)

    if log_message:
        if log_context:
            log_message = log_message.format(**log_context)
        msg = '%s %s' % (msg, log_message)
    
    log.error(msg)

    return parse_isotime(timestamp)


def parse_isotime(timestamp):
    m = _isotime_re.match(timestamp)
    if m:
        return datetime(*(x or 0 for x in m.groups()))
    else:
        raise ValueError('cannot parse timestamp', timestamp)

