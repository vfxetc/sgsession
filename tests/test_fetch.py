from .utils import *


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)


class TestFetch(TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.seq = sg.create('Sequence', dict(code=cls.__name__ + '.seq', project=project))
        cls.shot = sg.create('Shot', dict(code=cls.__name__ + '.shot', sg_sequence=cls.seq, project=project))
        
    def test_fetch_scalars(self):
        shot = self.session.find_one('Shot', [
            ('code', 'is', self.shot['code']),
            ('project', 'is', {'type': 'Project', 'id': project['id']}),
        ])
        self.assert_('description' not in shot)
        
        desc = shot.fetch('description')
        code, time, dne = shot.fetch(['code', 'created_at', 'does_not_exist'])
        
        self.assertEqual(shot['code'], self.shot['code'])
        self.assertEqual(code, self.shot['code'])
        
        self.assertEqual(shot['description'], None)
        self.assertEqual(desc, None)
        
        self.assert_(shot['created_at'])
        self.assert_(time)
        
        self.assert_('does_not_exist' not in shot)
        self.assert_(dne is None)
        
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
        
