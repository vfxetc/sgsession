from common import *


class TestRecursion(TestCase):

    def test_merge_recursion(self):

        s = Session()

        a = {'type': 'Shot', 'id': 1}
        b = {'type': 'Version', 'id': 2}

        a['latest_version'] = b
        b['entity'] = a

        x = s.merge(a)
        self.assertIs(x, x['latest_version']['entity'])

