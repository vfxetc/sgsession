from .utils import *


def setUpModule():
    fixtures.setup_tasks()
    globals().update(fixtures.__dict__)


class TestImportantFields(TestCase):
    
    def test_task_chain(self):
                
        task = self.session.merge(fixtures.tasks[0])
        shot = self.session.merge(fixtures.shots[0])
        seq = self.session.merge(fixtures.sequences[0])
        proj = self.session.merge(fixtures.project)
        
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
        task = self.session.merge(fixtures.tasks[0])
        task.pprint()
        task.fetch_core()
        task.pprint()
        self.assert_('short_name' in task['step'])
