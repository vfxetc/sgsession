import cPickle as pickle

from common import *


class TestPickling(TestCase):

    def test_pickle_session(self):

        sg = Session(Shotgun())

        x = pickle.dumps(sg)

        sg = pickle.loads(x)

        # It lost it's Shotgun object.
        self.assertIs(sg._shotgun, None)

    def test_pickle_entity(self):

        sg = Session(False)
        e1 = sg.merge({'type': 'Dummy', 'id': 1234})

        e1['key'] = 'value'

        x = pickle.dumps(e1)
        e2 = pickle.loads(x)

        # It lost the extra "key".
        self.assertEqual(e2, {'type': 'Dummy', 'id': 1234})

    def test_pickle_session_identity(self):

        sg = Session(False)
        e1 = sg.merge({'type': 'Dummy', 'id': 1234})
        e2 = sg.merge({'type': 'Dummy', 'id': 5678})

        x = pickle.dumps([e1, e2])
        e1, e2 = pickle.loads(x)

        # The sessions are the same.
        self.assertIs(e1.session, e2.session)
