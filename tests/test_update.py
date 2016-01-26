from common import *


class TestUpdate(TestCase):
    
    def setUp(self):
        
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        
        self.proj = fix.create('Project', dict(
            name=mini_uuid(),
            sg_description='Test project - ' + timestamp()
        ))
    
    def tearDown(self):
        self.fix.delete_all()
        
    def test_update_method_apis(self):

        seq = self.session.merge(self.fix.create('Sequence', dict(code='start', project=self.proj)))

        self.session.update('Sequence', seq['id'], {'code': 'shotgun_api3'})
        self.assertEqual(seq['code'], 'shotgun_api3')

        self.session.update('Sequence', seq['id'], code='kwarg_value')
        self.assertEqual(seq['code'], 'kwarg_value')

        self.session.update('Sequence', id=seq['id'], code='kwarg_id')
        self.assertEqual(seq['code'], 'kwarg_id')

        self.session.update(type='Sequence', id=seq['id'], code='kwarg_type')
        self.assertEqual(seq['code'], 'kwarg_type')

        self.session.update(seq, code='entity')
        self.assertEqual(seq['code'], 'entity')

    def test_update_batch_apis(self):

        seq1 = self.session.merge(self.fix.create('Sequence', dict(code='start', project=self.proj)))
        seq2 = self.session.merge(self.fix.create('Sequence', dict(code='start', project=self.proj)))

        res = self.session.update([seq1, seq2], code='list')
        self.assertEqual(len(res), 2)
        self.assertIs(res[0], seq1)
        self.assertIs(res[1], seq2)
        self.assertEqual(seq1['code'], 'list')
        self.assertEqual(seq2['code'], 'list')



