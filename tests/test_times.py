from common import *

from sgsession.utils import parse_isotime


class TestTimes(TestCase):

    def test_formats(self):
        parse_isotime('2015-12-09 12:42:00')
        parse_isotime('2015-12-09T12:42:00')
        parse_isotime('2015-12-09 12:42:00Z')
        parse_isotime('2015-12-09T12:42:00Z')
        parse_isotime('2015-12-09 12:42:00 UTC')
        parse_isotime('2015-12-09T12:42:00 UTC')
        parse_isotime('2015-12-09 12:42:00+0000')
        parse_isotime('2015-12-09T12:42:00+0000')

    def test_ranges(self):
        parse_isotime('0001-01-01 00:00:00')
        parse_isotime('9999-12-31 23:59:59')
        self.assertRaises(ValueError, parse_isotime, '0000-01-01 00:00:00') # datetime throws this one
        self.assertRaises(ValueError, parse_isotime, '0000-00-01 00:00:00')
        self.assertRaises(ValueError, parse_isotime, '0000-01-00 00:00:00')
        self.assertRaises(ValueError, parse_isotime, '9999-12-31 24:59:59')
        self.assertRaises(ValueError, parse_isotime, '9999-12-31 23:60:59')
        self.assertRaises(ValueError, parse_isotime, '9999-12-31 23:59:60')
