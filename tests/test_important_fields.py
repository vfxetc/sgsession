from common import *


class TestImportantFields(TestCase):
    
    def setUp(self):
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        proj = fix.Project(mini_uuid())
        seq = proj.Sequence('AA', project=proj)
        shot = seq.Shot('AA_001', project=proj)
        step = fix.find_or_create('Step', short_name='Anim')
        task = shot.Task('Animate something', step=step, project=proj)
        
        self.proj = minimal(proj)
        self.seq = minimal(seq)
        self.shot = minimal(shot)
        self.step = minimal(step)
        self.task = minimal(task)
    
    def tearDown(self):
        self.fix.delete_all()
        
    def test_task_chain(self):
                
        task = self.session.merge(self.task)
        shot = self.session.merge(self.shot)
        seq = self.session.merge(self.seq)
        proj = self.session.merge(self.proj)
        
        self.assert_('entity' not in task)
        self.assert_('project' not in task)
        self.assert_('step' not in task)
        self.assert_('code' not in shot)
        self.assert_('sg_sequence' not in shot)
        self.assert_('project' not in shot)
        self.assert_('code' not in seq)
        self.assert_('project' not in seq)
        self.assert_('name' not in proj)
        
        task.pprint()
        shot.pprint()
        seq.pprint()
        proj.pprint()
        print
        
        task.fetch_core()
        
        task.pprint()
        shot.pprint()
        seq.pprint()
        proj.pprint()
        print
        
        self.assert_('entity' in task)
        self.assert_('project' in task)
        self.assert_('step' in task)
        self.assert_('code' not in shot)
        self.assert_('sg_sequence' not in shot)
        self.assert_('project' not in shot)
        self.assert_('code' not in seq)
        self.assert_('project' not in seq)
        self.assert_('name' in proj) # <- Automatically by Shotgun.
                
        task.pprint()
        print
        
        self.session.fetch_heirarchy([task])
        task.pprint()
        
        self.assert_('code' in shot)
        self.assert_('sg_sequence' in shot)
        self.assert_('project' in shot)
        self.assert_('code' in seq)
        self.assert_('project' in seq)
        self.assert_('name' in proj)
    
    def test_important_deep(self):
        task = self.session.merge(self.task)
        task.pprint()
        task.fetch_core()
        task.pprint()
        self.assert_('short_name' in task['step'])
