from pprint import pprint

import shotgun_api3_registry

from sgmock import TestCase as BaseTestCase

from sgsession import Session, Entity
from sgsession import fixtures


class TestCase(BaseTestCase):

    def setUp(self):
        self.session = Session(fixtures.sg)
