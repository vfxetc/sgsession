from .utils import *


def setUpModule():
    fixtures.setup_sequences()
    globals().update(fixtures.__dict__)
    
    
class TestExports(TestCase):
    
    def test_minimal(self):
        
        shot = self.session.merge(fixtures.shots[0])
        shot.fetch_heirarchy()
        
        self.assertEqual(shot.minimal, dict(
            type="Shot",
            id=fixtures.shots[0]['id'],
        ))
        
        shot.pprint()
        print
        
        flat = shot.as_dict()
        pprint(flat)
        print
        
        self.assert_(len(flat['project']) > 2)
        self.assert_(len(flat['sg_sequence']['project']) == 2)
        
