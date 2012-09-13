from common import *


class TestMerge(TestCase):
    
    def setUp(self):
        self.session = Session(None)

    def test_setitem(self):
        a = self.session.merge(dict(a=1))
        a['child'] = dict(b=2)
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_setdefault(self):
        a = self.session.merge(dict(a=1))
        a.setdefault('child', dict(b=2))
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_recursive_update(self):
        a = self.session.merge(dict(a=1, child=dict(type='Sequence')))
        self.assert_(isinstance(a, Entity))
        self.assert_(isinstance(a['child'], Entity))
        
    def test_simple_update(self):
        a = self.session.merge(dict(a=1))
        b = self.session.merge(dict(b=2))
        a.update(b)
        self.assertEqual(a, self.session.merge(dict(a=1, b=2)))
    
    def test_complex_update(self):
        a = self.session.merge(dict(sequence=dict(x=0, a=1)))
        b = self.session.merge(dict(sequence=dict(x=3, b=2)))
        a.update(b)
        self.assertEqual(a, self.session.merge(dict(sequence=dict(a=1, b=2, x=3))))

    def test_multiple(self):
        a, b = self.session.merge((dict(a=1), dict(b=2)))
        self.assertEqual(a, self.session.merge(dict(a=1)))
        self.assertEqual(b, self.session.merge(dict(b=2)))