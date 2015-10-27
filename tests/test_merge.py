from common import *


def dummy(**kwargs):
    dummy.count += 1
    kwargs.setdefault('type', 'Dummy')
    kwargs.setdefault('id', dummy.count)
    return kwargs
dummy.count = 0

class TestMerge(TestCase):
    
    def setUp(self):
        self.session = Session(False)
    
    def merge(self, *args, **kwargs):
        for arg in args:
            kwargs.update(arg)
        return self.session.merge(kwargs)
    
    def test_non_entities(self):
        data = self.merge(key='value')
        self.assertFalse(isinstance(data, Entity))
        data = self.merge(type='Dummy')
        self.assertFalse(isinstance(data, Entity))
        data = self.merge(id=123)
        self.assertFalse(isinstance(data, Entity))
        
    def test_merge_via_setitem(self):
        entity = self.merge(dummy(x=1))
        entity['child'] = dummy(x=2)
        self.assertEqual(entity['child']['x'], 2)
        self.assertIsInstance(entity['child'], Entity)
    
    def test_merge_via_setdefault(self):
        entity = self.merge(dummy(x=1))
        entity.setdefault('child', dummy(x=2))
        self.assertEqual(entity['child']['x'], 2)
        self.assertIsInstance(entity['child'], Entity)
    
    def test_merge_via_recursive_update(self):
        entity = self.merge(dummy(x=1, child=dummy(x=2)))
        self.assertIsInstance(entity, Entity)
        self.assertIsInstance(entity['child'], Entity)
        
    def test_merge_via_simple_update(self):
        a = self.merge(a=1)
        b = self.merge(b=2)
        a.update(b)
        self.assertEqual(a, self.merge(a=1, b=2))
    
    def test_merge_via_complex_update(self):
        
        # Non entity-dicts are replaced.
        a = self.merge(dummy(sequence=dict(x=0, a=1)))
        b = dict(sequence=dict(x=3, b=2))
        a.update(b)
        self.assertEqual(a['sequence'], dict(x=3, b=2))
        
        # Entity dicts are updated.
        a = self.merge(dummy(sequence=dict(type='DummyChild', id=1, x=0, a=1)))
        b = dict(sequence=dict(type='DummyChild', id=1, x=3, b=2))
        a.update(b)
        self.assertEqual(a['sequence'], dict(type='DummyChild', id=1, x=3, a=1, b=2))
    
    def test_multiple(self):
        a, b = self.session.merge((dict(a=1), dict(b=2)))
        self.assertEqual(a, self.merge(a=1))
        self.assertEqual(b, self.merge(b=2))
    
    def test_list_entities(self):
        a = self.merge(dummy())
        b = self.merge(dummy())
        entity = self.merge(dummy(children=[a.minimal, b.minimal]))
        self.assertEqual(entity['children'], [a, b])
        self.assertIs(entity['children'][0], a)
        
    def test_tuple_entities(self):
        a = self.merge(dummy())
        b = self.merge(dummy())
        entity = self.merge(dummy(children=(a.minimal, b.minimal)))
        self.assertEqual(entity['children'], (a, b))
        self.assertIs(entity['children'][0], a)
    
    def test_list_entity_reset(self):
        a = self.merge(dummy())
        b = self.merge(dummy())
        c = self.merge(dummy())
        entity = self.merge(dummy(children=[a.minimal, b.minimal]))
        updated = entity.as_dict()
        updated['children'] = [b.minimal, c.minimal]
        entity2 = self.merge(updated)
        self.assertIs(entity, entity2)
        self.assertEqual(entity['children'], [b, c])
        
    def test_list_entity_indirect_update(self):
        a = self.merge(dummy(x=1))
        b = self.merge(dummy())
        entity = self.merge(dummy(children=[a.minimal, b.minimal]))
        updated = a.minimal
        updated['x'] = 2
        entity2 = self.merge(dummy(link=[updated]))
        self.assertIs(a, entity['children'][0])
        self.assertIs(a, entity2['link'][0])
        self.assertEqual(a['x'], 2)
        
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


class TestLiveUpdates(TestCase):
    
    def setUp(self):
        self.shotgun = Shotgun()
        self.session = Session(self.shotgun)
    
    def test_has_times(self):
        e = self.session.create('Project', {'name': mini_uuid()})
        self.assertIn('updated_at', e)
        
    def test_updates_merge(self):
        e = self.session.create('Project', {'name': mini_uuid()})
        self.session.update('Project', e['id'], {'name': e['name'] + ' 2'})
        self.assertEqual(e['name'][-2:], ' 2')

