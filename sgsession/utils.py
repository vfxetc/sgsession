from datetime import datetime
import re
import itertools


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


def parse_isotime(x):
    if isinstance(x, basestring):
        try:
            return datetime.strptime(x, '%Y-%m-%d %H:%M:%S %Z')
        except ValueError:
            return datetime.strptime(x, '%Y-%m-%d %H:%M:%S')
    else:
        return x

