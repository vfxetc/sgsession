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
    
