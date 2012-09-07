from .utils import *


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)


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

