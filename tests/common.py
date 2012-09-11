from pprint import pprint, pformat
import datetime
import os

import shotgun_api3

from sgmock import Shotgun, ShotgunError, Fault
from sgmock import Fixture
from sgmock import TestCase

from sgsession import Session, Entity


def mini_uuid():
    return os.urandom(4).encode('hex')

def timestamp():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

def minimal(entity):
    return dict(type=entity['type'], id=entity['id'])
