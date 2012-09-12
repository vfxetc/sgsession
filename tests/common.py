from pprint import pprint, pformat
import datetime
import os

from sgmock import Fixture
from sgmock import TestCase

if 'USE_SHOTGUN' in os.environ:
    from shotgun_api3 import ShotgunError, Fault
    import shotgun_api3_registry
    def Shotgun():
        return shotgun_api3_registry.connect('sgsession.tests', server='testing')
else:
    from sgmock import Shotgun, ShotgunError, Fault

from sgsession import Session, Entity


def mini_uuid():
    return os.urandom(4).encode('hex')

def timestamp():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

def minimal(entity):
    return dict(type=entity['type'], id=entity['id'])
