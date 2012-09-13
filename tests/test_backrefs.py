from common import *
    
class TestBackrefs(TestCase):
    
    def setUp(self):
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        proj = fix.Project(mini_uuid())
        seqs = [proj.Sequence(code, project=proj) for code in ('AA', 'BB')]
        shots = [seq.Shot('%s_%03d' % (seq['code'], i), project=proj) for seq in seqs for i in range(1, 3)]
        steps = [fix.find_or_create('Step', code=code, short_name=code) for code in ('Anm', 'Comp', 'Model')]
        tasks = [shot.Task(step['code'] + ' something', step=step, entity=shot, project=proj) for step in steps for shot in shots]
        
        self.proj = minimal(proj)
        self.seqs = [minimal(x) for x in seqs]
        self.shots = [minimal(x) for x in shots]
        self.steps = [minimal(x) for x in steps]
        self.tasks = [minimal(x) for x in tasks]
    
    def tearDown(self):
        self.fix.delete_all()
    
    def test_backref(self):
        seq = self.session.merge(self.seqs[0])
        proj = self.session.merge(self.proj)
        
        self.assert_(('Shot', 'sg_sequence') not in seq.backrefs)
        self.assert_(('Shot', 'project') not in proj.backrefs)
        self.assert_(('Sequence', 'project') not in proj.backrefs)
        
        proj.pprint(backrefs=True)
        seq.pprint(backrefs=True)
        print
        
        shots = self.session.find('Shot', [('sg_sequence', 'is', seq)])
        
        proj.pprint(backrefs=True)
        seq.pprint(backrefs=True)
        for x in shots:
            x.pprint(backrefs=True)
        print
        
        self.assert_(('Shot', 'sg_sequence') in seq.backrefs)
        for shot in seq.backrefs[('Shot', 'sg_sequence')]:
            self.assert_(shot['sg_sequence'] is seq)
        
        seq.project()
        self.assertEqual(len(shots), len(proj.backrefs[('Shot', 'project')]))
        for shot in proj.backrefs[('Shot', 'project')]:
            self.assert_(shot['project'] is proj)
        self.assertEqual(1, len(proj.backrefs[('Sequence', 'project')]))
        for seq in proj.backrefs[('Sequence', 'project')]:
            self.assert_(seq['project'] is proj)
        
    def test_fetch_backref(self):
        
        proj = self.session.merge(self.proj)
        seqs = [self.session.merge(x) for x in self.seqs]
        shots = [self.session.merge(x) for x in self.shots]
        
        self.assert_(('Shot', 'project') not in proj.backrefs)
        self.assert_(('Sequence', 'project') not in proj.backrefs)
        
        proj.fetch_backrefs('Shot', 'project')
        proj.pprint(backrefs=True)
        
        self.assertEqual(len(shots), len(proj.backrefs[('Shot', 'project')]))
        for shot in proj.backrefs[('Shot', 'project')]:
            self.assert_(shot['project'] is proj)
        
        proj.fetch_backrefs('Sequence', 'project')
        
        self.assertEqual(len(seqs), len(proj.backrefs[('Sequence', 'project')]))
        for seq in proj.backrefs[('Sequence', 'project')]:
            self.assert_(seq['project'] is proj)
