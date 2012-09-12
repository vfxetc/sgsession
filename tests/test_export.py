from common import *
    
    
class TestExports(TestCase):
    
    def setUp(self):
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        proj = fix.Project(mini_uuid())
        seqs = [proj.Sequence(code, project=proj) for code in ('AA', 'BB')]
        shots = [seq.Shot('%s_%03d' % (seq['code'], i), project=proj) for seq in seqs for i in range(1, 3)]
        
        self.proj = minimal(proj)
        self.seqs = [minimal(x) for x in seqs]
        self.shots = [minimal(x) for x in shots]
    
    def tearDown(self):
        self.fix.delete_all()
    
    def test_minimal(self):
        
        shot = self.session.merge(self.shots[0])
        shot.fetch_heirarchy()
        
        self.assertEqual(shot.minimal, dict(
            type="Shot",
            id=self.shots[0]['id'],
        ))
        
        shot.pprint()
        print
        
        flat = shot.as_dict()
        pprint(flat)
        print
        
        self.assert_(len(flat['project']) > 2)
        self.assert_(len(flat['sg_sequence']['project']) == 2)
        
