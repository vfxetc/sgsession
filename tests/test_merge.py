from common import *


class TestMerge(TestCase):
    
    def setUp(self):
        self.session = Session(None)
    
    def merge(self, **kwargs):
        return self.session.merge(kwargs)
    
    def test_setitem(self):
        a = self.merge(a=1)
        a['child'] = dict(b=2)
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_setdefault(self):
        a = self.merge(a=1)
        a.setdefault('child', dict(b=2))
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_recursive_update(self):
        a = self.merge(a=1, child=dict(type='Sequence'))
        self.assert_(isinstance(a, Entity))
        self.assert_(isinstance(a['child'], Entity))
        
    def test_simple_update(self):
        a = self.merge(a=1)
        b = self.merge(b=2)
        a.update(b)
        self.assertEqual(a, self.merge(a=1, b=2))
    
    def test_complex_update(self):
        a = self.merge(sequence=dict(x=0, a=1))
        b = self.merge(sequence=dict(x=3, b=2))
        a.update(b)
        self.assertEqual(a, self.merge(sequence=dict(a=1, b=2, x=3)))

    def test_multiple(self):
        a, b = self.session.merge((dict(a=1), dict(b=2)))
        self.assertEqual(a, self.merge(a=1))
        self.assertEqual(b, self.merge(b=2))
    
    def test_over_never(self):
        
        a = self.session.merge(dict(type='Dummy', id=1, v='a'))
        b = self.session.merge(dict(type='Dummy', id=1, v='b'), over=False)
        self.assertEqual(a['v'], 'a')
        
        a = self.session.merge(dict(type='Dummy', id=2, v='a', updated_at=1))
        b = self.session.merge(dict(type='Dummy', id=2, v='b', updated_at=2), over=False)
        self.assertEqual(a['v'], 'a')
        
        a = self.session.merge(dict(type='Dummy', id=3, v='a', updated_at=2))
        b = self.session.merge(dict(type='Dummy', id=3, v='b', updated_at=1), over=False)
        self.assertEqual(a['v'], 'a')
    
    def test_over_timed(self):
        
        a = self.session.merge(dict(type='Dummy', id=4, v='a', updated_at=1))
        b = self.session.merge(dict(type='Dummy', id=4, v='b', updated_at=2))
        self.assertEqual(a['v'], 'b')
        
        a = self.session.merge(dict(type='Dummy', id=5, v='a', updated_at=2))
        b = self.session.merge(dict(type='Dummy', id=5, v='b', updated_at=1))
        self.assertEqual(a['v'], 'a')
    
    def test_over_always(self):
    
        a = self.session.merge(dict(type='Dummy', id=6, v='a'))
        b = self.session.merge(dict(type='Dummy', id=6, v='b'), over=True)
        self.assertEqual(a['v'], 'b')
        
        a = self.session.merge(dict(type='Dummy', id=7, v='a', updated_at=1))
        b = self.session.merge(dict(type='Dummy', id=7, v='b', updated_at=2), over=True)
        self.assertEqual(a['v'], 'b')
        
        a = self.session.merge(dict(type='Dummy', id=8, v='a', updated_at=2))
        b = self.session.merge(dict(type='Dummy', id=8, v='b', updated_at=1), over=True)
        self.assertEqual(a['v'], 'b')
    
    def test_over_deep(self):
        
        a = self.session.merge(dict(type='Dummy', id=9, child=dict(type='DummyChild', id=1, v='a', updated_at=1)))
        b = self.session.merge(dict(type='Dummy', id=9, child=dict(type='DummyChild', id=1, v='b', updated_at=2)))
        self.assertEqual(a['child']['v'], 'b')
        
        a = self.session.merge(dict(type='Dummy', id=10, child=dict(type='DummyChild', id=2, v='a', updated_at=2)))
        b = self.session.merge(dict(type='Dummy', id=10, child=dict(type='DummyChild', id=2, v='b', updated_at=1)))
        self.assertEqual(a['child']['v'], 'a')
        
        
        