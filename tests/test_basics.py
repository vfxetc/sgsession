from .utils import *


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)
    
    
class TestBasics(TestCase):

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
