from pprint import pprint
from unittest import TestCase as BaseTestCase

import shotgun_api3_registry

from sgsession import Session, Entity
from sgsession import fixtures


class TestCase(BaseTestCase):

    def setUp(self):
        self.session = Session(fixtures.sg)
