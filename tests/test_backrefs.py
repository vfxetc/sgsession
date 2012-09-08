from .utils import *


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)
    
    
class TestBackrefs(TestCase):

    def test_backref(self):
        seq = self.session.merge(fixtures.sequences[0])
        proj = self.session.merge(fixtures.project)
        
        self.assert_(('Shot', 'sg_sequence') not in seq.backrefs)
        self.assert_(('Shot', 'project') not in proj.backrefs)
        self.assert_(('Sequence', 'project') not in proj.backrefs)
        
        shots = self.session.find('Shot', [('sg_sequence', 'is', seq)])
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
        
        proj = self.session.merge(fixtures.project)
        seqs = [self.session.merge(x) for x in fixtures.sequences]
        shots = [self.session.merge(x) for x in fixtures.shots]
        
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
