from pprint import pprint
from unittest import TestCase as BaseTestCase

import shotgun_api3_registry

from sgsession import Session, Entity

from . import fixtures


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)
    

class TestCase(BaseTestCase):

    def setUp(self):
        self.session = Session(sg)
        

class TestEntityBasics(TestCase):

    def test_nonhashable(self):
        a = self.session.merge(a=1)
        self.assertRaises(TypeError, hash, a)
        b = self.session.merge(type="Dummy", id=1)
        self.assert_(hash(b))
    
    def test_sets(self):
        shots = list(self.session.merge(x) for x in fixtures.shots)
        shot_set = set(shots)
        self.assertEqual(len(shot_set), len(shots))
        
        self.assert_(shots[0] in shot_set)

        dummy = self.session.merge(type="Dummy", id=1)
        self.assert_(dummy not in shot_set)
        
        shot_set.add(shots[0])
        self.assertEqual(len(shot_set), len(shots))
        shot_set.add(dummy)
        self.assertEqual(len(shot_set), len(shots) + 1)
        

class TestEntityMerge(TestCase):

    def test_setitem(self):
        a = self.session.merge(a=1)
        a['child'] = dict(b=2)
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_setdefault(self):
        a = self.session.merge(a=1)
        a.setdefault('child', dict(b=2))
        self.assertEqual(a['child']['b'], 2)
        self.assert_(isinstance(a['child'], Entity))
    
    def test_recursive_update(self):
        a = self.session.merge(a=1, child=dict(type='Sequence'))
        self.assert_(isinstance(a, Entity))
        self.assert_(isinstance(a['child'], Entity))
        
    def test_simple_update(self):
        a = self.session.merge(a=1)
        b = self.session.merge(b=2)
        a.update(b)
        self.assertEqual(a, self.session.merge(a=1, b=2))
    
    def test_complex_update(self):
        a = self.session.merge(sequence=dict(x=0, a=1))
        b = self.session.merge(sequence=dict(x=3, b=2))
        a.update(b)
        self.assertEqual(a, self.session.merge(sequence=dict(a=1, b=2, x=3)))
    
    
class TestEntityFetch(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.seq = sg.create('Sequence', dict(code=cls.__name__ + '.seq', project=project))
        cls.shot = sg.create('Shot', dict(code=cls.__name__ + '.shot', sg_sequence=cls.seq, project=project))
        
    def test_fetch_scalar(self):
        shot = self.session.find_one('Shot', [
            ('code', 'is', self.shot['code']),
            ('project', 'is', {'type': 'Project', 'id': project['id']}),
        ])
        self.assert_('description' not in shot)
        shot.fetch(['code', 'description', 'created_at', 'does_not_exist'])
        self.assertEqual(shot['code'], self.shot['code'])
        self.assertEqual(shot['description'], None)
        self.assert_(shot['created_at'])
        self.assert_('does_not_exist' not in shot)
    
    def test_fetch_entity(self):
        
        shot = self.session.find_one('Shot', [('id', 'is', self.shot['id'])])
                
        shot.fetch('created_at')
        self.assert_(shot['created_at'])
        
        shot['project'].fetch(['sg_description'])
        self.assert_(shot['project']['sg_description'])
        
        project_entity = self.session.find_one('Project', [
            ('id', 'is', project['id']),
        ])
        self.assert_(project_entity is shot['project'])
    
    def test_parents(self):
        
        shot = self.session.find_one('Shot', [
            ('code', 'is', self.shot['code']),
            ('project', 'is', {'type': 'Project', 'id': project['id']}),
        ])
                
        seq = shot.parent()
        self.assertEqual(seq['id'], self.seq['id'])
        
        proj = seq.parent()
        self.assertEqual(proj['id'], project['id'])
        
        shot.fetch(['project'])
        self.assert_(shot['project'] is proj)
        

class TestHeirarchy(TestCase):
    
    def test_fetch_shot_heirarchy(self):
        
        shots = [self.session.merge(x) for x in fixtures.shots]
        seqs = [self.session.merge(x) for x in fixtures.sequences]
        proj = self.session.merge(fixtures.project)
        
        self.session.fetch_heirarchy(shots)
        
        for x in shots:
            x.pprint()
            print
        
        self.assertEqual(shots[0].parent()['id'], sequences[0]['id'])
        self.assertEqual(shots[1].parent()['id'], sequences[0]['id'])
        self.assertEqual(shots[2].parent()['id'], sequences[1]['id'])
        self.assertEqual(shots[3].parent()['id'], sequences[1]['id'])
        
        for shot in shots[1:]:
            self.assert_(shot.parent().parent() is shots[0].parent().parent())
        
        self.assert_(shots[0].parent() is shots[1].parent())
        self.assert_(shots[0].parent() is not shots[2].parent())
        self.assert_(shots[2].parent() is shots[3].parent())
        
        # Backrefs
        for seq in seqs:
            self.assert_(seq in proj.backrefs[('Sequence', 'project')])
        for shot in shots:
            self.assert_(shot in proj.backrefs[('Shot', 'project')])


class TestImportantFields(TestCase):
    
    def test_task_chain(self):
        
        task = self.session.merge(fixtures.tasks[0])
        shot = self.session.merge(fixtures.shots[0])
        seq = self.session.merge(fixtures.sequences[0])
        proj = self.session.merge(fixtures.project)
        
        self.assert_('entity' not in task)
        self.assert_('project' not in task)
        self.assert_('step' not in task)
        self.assert_('code' not in shot)
        self.assert_('sg_sequence' not in shot)
        self.assert_('project' not in shot)
        self.assert_('code' not in seq)
        self.assert_('project' not in seq)
        self.assert_('name' not in proj)
        
        task.pprint()
        shot.pprint()
        seq.pprint()
        proj.pprint()
        print
        
        task.fetch_core()
        
        self.assert_('entity' in task)
        self.assert_('project' in task)
        self.assert_('step' in task)
        self.assert_('code' not in shot)
        self.assert_('sg_sequence' not in shot)
        self.assert_('project' not in shot)
        self.assert_('code' not in seq)
        self.assert_('project' not in seq)
        self.assert_('name' in proj) # <- Automatically by Shotgun.
        
        task.pprint()
        print
        
        self.session.fetch_heirarchy([task])
        task.pprint()
        
        self.assert_('code' in shot)
        self.assert_('sg_sequence' in shot)
        self.assert_('project' in shot)
        self.assert_('code' in seq)
        self.assert_('project' in seq)
        self.assert_('name' in proj)

        