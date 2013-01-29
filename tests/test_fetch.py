from common import *


class TestFetch(TestCase):
    
    def setUp(self):
        
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        self.proj = fix.create('Project', dict(
            name=mini_uuid(),
            sg_description='Test project - ' + timestamp()
        ))
        self.seq = fix.create('Sequence', dict(code=self.__class__.__name__ + '_seq', project=self.proj))
        self.shot = fix.create('Shot', dict(code=self.__class__.__name__ + '_shot', sg_sequence=self.seq, project=self.proj))
    
    def tearDown(self):
        self.fix.delete_all()
        
    def test_fetch_scalars(self):
        shot = self.session.find_one('Shot', [
            ('code', 'is', self.shot['code']),
            ('project', 'is', {'type': 'Project', 'id': self.proj['id']}),
        ])
        self.assert_('description' not in shot)
        
        desc = shot.fetch('description')
        code, time, dne = shot.fetch(['code', 'created_at', 'does_not_exist'])
        
        self.assertEqual(shot['code'], self.shot['code'])
        self.assertEqual(code, self.shot['code'])
        
        self.assertEqual(shot.get('description'), None)
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
            ('id', 'is', self.proj['id']),
        ])
        self.assert_(project_entity is shot['project'])
    
    def test_parents(self):
        
        shot = self.session.find_one('Shot', [
            ('code', 'is', self.shot['code']),
            ('project', 'is', {'type': 'Project', 'id': self.proj['id']}),
        ])
                
        seq = shot.parent()
        self.assertSameEntity(seq, self.seq)
        
        proj = seq.parent()
        self.assertSameEntity(proj, self.proj)
        
        shot.fetch(['project'])
        self.assertIs(shot['project'], proj)

    def test_implicit_links(self):

        shot = self.session.find_one('Shot', [('id', 'is', self.shot['id'])], ['sg_sequence.Sequence.sg_status_list'])

        self.assertSameEntity(shot, self.shot)

        # This is the critical one, as we only requested a field off of the
        # sequence and not the whole thing.
        self.assertSameEntity(shot['sg_sequence'], self.seq)

        
