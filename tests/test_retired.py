import warnings

from common import *


class TestRetired(TestCase):

    def setUp(self):
        sg = Shotgun()
        self.sg = self.fix = fix = Fixture(sg)
        self.session = Session(self.sg)
        self.proj = fix.Project(mini_uuid())
    
    def tearDown(self):
        self.fix.delete_all()

    def test_retired_instance_fetch(self):

        seq = self.proj.Sequence('About_To_Retire', sg_status_list='rev')
        seq = self.session.merge(seq)
        self.sg.delete('Sequence', seq['id'])

        # Force it to have to get it from the server again.
        del seq['sg_status_list']

        with warnings.catch_warnings(record=True) as w:
            self.assertIs(None, seq.fetch('sg_status_list'))

        self.assertEqual(1, len(w), 'No warning was issued.')
        self.assertEqual(w[0].message.args[0], 'Sequence %d was not found' % seq['id'])


