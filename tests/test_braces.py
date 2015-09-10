from common import *

from sgsession.utils import expand_braces


class TestExpandBraces(TestCase):

    def test_expand_braces(self):

        self.assertEqual(expand_braces('a'),
            ['a'])

        self.assertEqual(expand_braces('{a,b}'),
            ['a', 'b'])

        self.assertEqual(expand_braces('{a,b}_{c,d}'),
            ['a_c', 'a_d', 'b_c', 'b_d'])

        self.assertEqual(expand_braces('pre_{a,b}_post'),
            ['pre_a_post', 'pre_b_post'])
    