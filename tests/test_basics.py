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
        self.session.find('Shot', [('sg_sequence', 'is', seq)])
        self.assert_(('Shot', 'sg_sequence') in seq.backrefs)
        for shot in seq.backrefs[('Shot', 'sg_sequence')]:
            self.assert_(shot['sg_sequence'] is seq)
        
        seq.pprint(backrefs=False)
        print
        seq.project().pprint(backrefs=5)
        self.assert_(False)
