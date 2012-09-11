from common import *


class TestHeirarchy(TestCase):
    
    def setUp(self):
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        proj = fix.Project(mini_uuid())
        seqs = [proj.Sequence(code, project=proj) for code in ('AA', 'BB')]
        shots = [seq.Shot('%s_%03d' % (seq['code'], i), project=proj) for seq in seqs for i in range(1, 3)]
        steps = [fix.find_or_create('Step', name=name, short_name=name) for name in ('Anm', 'Comp', 'Model')]
        tasks = [shot.Task(step['name'] + ' something', step=step, entity=shot, project=proj) for step in steps for shot in shots]
        
        self.proj = minimal(proj)
        self.seqs = [minimal(x) for x in seqs]
        self.shots = [minimal(x) for x in shots]
        self.steps = [minimal(x) for x in steps]
        self.tasks = [minimal(x) for x in tasks]
    
    def test_fetch_shot_heirarchy(self):
        
        shots = [self.session.merge(x) for x in self.shots]
        seqs = [self.session.merge(x) for x in self.seqs]
        proj = self.session.merge(self.proj)
        
        self.session.fetch_heirarchy(shots)
        
        for x in shots:
            x.pprint()
            print
        
        self.assertSameEntity(shots[0].parent(), self.seqs[0])
        self.assertSameEntity(shots[1].parent(), self.seqs[0])
        self.assertSameEntity(shots[2].parent(), self.seqs[1])
        self.assertSameEntity(shots[3].parent(), self.seqs[1])
        
        for shot in shots[1:]:
            self.assertIs(shot.parent().parent(), shots[0].parent().parent())
        
        self.assertIs(shots[0].parent(), shots[1].parent())
        self.assertIsNot(shots[0].parent(), shots[2].parent())
        self.assertIs(shots[2].parent(), shots[3].parent())
        
        # Backrefs
        for seq in seqs:
            self.assertIn(seq, proj.backrefs[('Sequence', 'project')])
        for shot in shots:
            self.assertIn(shot, proj.backrefs[('Shot', 'project')])

