from datetime import datetime
import functools
import itertools
import logging
import re

import pkg_resources


log = logging.getLogger(__name__)


class cached_property(object):
    
    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func
    
    def __get__(self, instance, owner_type=None):
        if instance is None:
            return self
        try:
            return instance.__dict__[self.__name__]
        except KeyError:
            value = self.func(instance)
            instance.__dict__[self.__name__] = value
            return value


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


def shotgun_api3_connect(*args, **kwargs):

    eps = []
    for ep in pkg_resources.iter_entry_points('shotgun_api3_connect'):
        eps.append((ep, True))
    for ep in pkg_resources.iter_entry_points('shotgun_api3_kwargs'):
        eps.append((ep, False))
    eps.sort(key=lambda (ep, _): ep.name)

    for ep, is_direct in eps:

        func = ep.load()
        res = func(*args, **kwargs)
        if not res:
            continue

        if is_direct:
            return res

        import shotgun_api3
        return shotgun_api3.Shotgun(**res)

    # Fall back onto the shotgun_api3_registry module.
    try:
        import shotgun_api3_registry as m
    except ImportError:
        pass
    else:
        return m.connect(*args, **kwargs)

    raise ValueError("No shotgun_api3_connect/shotgun_api3_kwargs entry point or shotgun_api3_registry module found.")


# We don't need to be so precise about the ranges of minutes/seconds, etc.,
# because datetime deals with it.
_isotime_re = re.compile(r'''
    ^
    (\d{4}) # year
    \D?
    (\d{2}) # month: 01 to 12
    \D?
    (\d{2}) # day
    \D? # a "T" or space
    (\d{2}) # hours
    \D?
    (\d{2}) # minutes
    \D?
    (\d{2}) # seconds
    (?:\.(\d{1,6}))? # microsecond
    \D? # a "Z" or space
    (?:
        \d{4} | # offset
        \D{3,}  # named
    )? # ignored
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

    return _parse_isotime(timestamp)


def parse_isotime(timestamp):
    if not isinstance(timestamp, basestring):
        return timestamp
    return _parse_isotime(timestamp)


def _parse_isotime(timestamp):
    m = _isotime_re.match(timestamp)
    if m:
        return datetime(*(int(x or 0) for x in m.groups()))
    else:
        raise ValueError('cannot parse timestamp', timestamp)

