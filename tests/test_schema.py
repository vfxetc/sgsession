from common import *

from sgschema import Schema


class TestSchema(TestCase):
    
    def setUp(self):

        self.schema = schema = Schema()
        schema.load({
            'entities': {
                'Project': {},
                'Asset': {},
                'Sequence': {
                    'fields': {},
                    'field_aliases': {
                        'parent': 'project'
                    },
                },
                'Shot': {
                    'fields': {},
                    'field_aliases': {
                        'parent': 'sg_sequence',
                        'length': 'sg_shot_length',
                    },
                },
                'Task': {
                    'fields': {},
                    'field_aliases': {
                        'shot': 'entity',
                    },
                },
                'PublishEvent': {
                    'fields': {
                        'sg_version': {},
                        'sg_link': {},
                        'sg_source_publishes': {},
                    },
                    'field_aliases': {
                        'sources': 'sg_source_publishes',
                    },
                },
            },
            'entity_aliases': {
                #
            },
            'entity_tags': {
                #
            },
        })

        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        
        proj = fix.Project(mini_uuid())
        seq = proj.Sequence('AA', project=proj)
        shot = seq.Shot('AA_001', sg_sequence=seq, sg_shot_length=1234, project=proj)
        #step = fix.find_or_create('Step', short_name='Anim')
        #task = shot.Task('Animate something', step=step, project=proj)
        
        self.proj = minimal(proj)
        self.seq = minimal(seq)
        self.shot = minimal(shot)
        #self.step = minimal(step)
        #self.task = minimal(task)
    
    def tearDown(self):
        self.fix.delete_all()

    def new_session(self):
        return Session(self.sg, schema=self.schema)

    def test_get_alias(self):
        session = self.new_session()
        
        seq = session.find_one('Sequence', [], ['project'])
        seq.pprint()

        self.assertIn('project', seq)
        self.assertIn('$parent', seq)
        self.assertIs(seq['project'], seq['$parent'])

        self.assertNotIn('not_a_field', seq)

    def test_return_field_alias(self):
        session = self.new_session()

        shot = session.find_one('Shot', [], ['$length'])
        self.assertEqual(shot['sg_shot_length'], 1234)
        self.assertEqual(shot['$length'], 1234)

    def test_find_filter_alias(self):
        session = self.new_session()
        shot = session.find_one('Shot', [('$length', 'is', 1234)])
        self.assertSameEntity(shot, self.shot)

    def test_create_and_update_alias(self):
        session = self.new_session()

        task = session.create('Task', {'$shot': self.shot})
        self.assertSameEntity(task['entity'], self.shot)

        a = session.create('PublishEvent', {'name': 'a', 'link': task})
        self.assertSameEntity(a['sg_link'], task)

        b = session.create('PublishEvent', {'name': 'b', 'link': task, '$sources': [a]})
        self.assertSameEntity(b['sg_link'], task)
        self.assertSameEntity(b['sg_source_publishes'][0], a)

        session.update('PublishEvent', b['id'], {'version': 99})
        self.assertEqual(b['sg_version'], 99)





