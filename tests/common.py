from pprint import pprint, pformat
import datetime
import os

from sgmock import Fixture
from sgmock import TestCase

_shotgun_server = os.environ.get('SHOTGUN', 'mock')
if _shotgun_server == 'mock':
    from sgmock import Shotgun, ShotgunError, Fault
else:
    from shotgun_api3 import ShotgunError, Fault
    import shotgun_api3_registry
    def Shotgun():
        return shotgun_api3_registry.connect('sgsession.tests', server=_shotgun_server)

from sgsession import Session, Entity


def mini_uuid():
    return os.urandom(4).encode('hex')

def timestamp():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

def minimal(entity):
    return dict(type=entity['type'], id=entity['id'])
