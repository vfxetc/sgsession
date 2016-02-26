from common import *


class TestOwnership(TestCase):
    
    def setUp(self):
        
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        self.proj = fix.create('Project', dict(
            name=mini_uuid(),
            sg_description='Test project - ' + timestamp()
        ))
    
    def test_ownership(self):
        
        sg1 = Session(self.sg)
        sg2 = Session(self.sg)
        
        a = sg1.get('Project', self.proj['id']) # No API here.
        
        self.assertRaises(ValueError, sg2.fetch, [a], ['content'])
