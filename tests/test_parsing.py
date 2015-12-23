from common import *


class TestParsing(TestCase):
    
    def setUp(self):
        self.sg = Shotgun()
        self.session = Session(self.sg)

    def test_only_digits(self):

        self.assertSameEntity(
            self.session.parse_user_input('12345', entity_types=['Version']),
            {'type': 'Version', 'id': 12345},
        )

        # Needs entity_types.
        self.assertRaises(ValueError, self.session.parse_user_input, '12345')

        # Needs single entity_types.
        self.assertRaises(ValueError, self.session.parse_user_input, '12345', entity_types=['A', 'B'])

    def test_json(self):
        self.assertSameEntity(
            self.session.parse_user_input('{"type":"Version","id":12345}'),
            {'type': 'Version', 'id': 12345},
        )
        self.assertRaises(ValueError, self.session.parse_user_input, '{"type":"Version","id":12345,}') # bad syntax
        self.assertRaises(ValueError, self.session.parse_user_input, '{"type":"Version","id":"12345"}') # bad ID
        self.assertRaises(ValueError, self.session.parse_user_input, '{"type":true,"id":12345}') # bad Type
        self.assertRaises(ValueError, self.session.parse_user_input, '{"id":12345}') # missing Type
        self.assertRaises(ValueError, self.session.parse_user_input, '{"id":"12345"}') # missing ID

    def test_detail_url(self):
        self.assertSameEntity(
            self.session.parse_user_input('https://example.shotgunstudio.com/detail/Version/12345#whatever'),
            {'type': 'Version', 'id': 12345},
        )

    def test_url_target(self):
        self.assertSameEntity(
            self.session.parse_user_input('https://example.shotgunstudio.com/page/999#Version_12345_Whatever'),
            {'type': 'Version', 'id': 12345},
        )

    def test_project_url(self):

        self.session.merge({'type': 'Page', 'id': 9000, 'project': {'type': 'Project', 'id': 12345}})
        self.assertSameEntity(
            self.session.parse_user_input('https://example.shotgunstudio.com/page/9000', fetch_project_from_page=True),
            {'type': 'Project', 'id': 12345},
        )

        # Needs the kwarg.
        self.assertRaises(ValueError, self.session.parse_user_input, 'https://example.shotgunstudio.com/page/9001')

        # Needs the entity to exist.
        self.assertRaises(ValueError, self.session.parse_user_input, 'https://example.shotgunstudio.com/page/999999', fetch_project_from_page=True)

        # Needs a project.
        self.session.merge({'type': 'Page', 'id': 9002, 'project': None})
        self.assertRaises(ValueError, self.session.parse_user_input, 'https://example.shotgunstudio.com/page/9002', fetch_project_from_page=True)

    def test_direct_variations(self):
        for islower in True, False:
            for sep in ':_- ':
                self.assertSameEntity(
                    self.session.parse_user_input('%s%s%s' % (
                        'version' if islower else 'Version',
                        sep,
                        '12345'
                    )),
                    {'type': 'Version', 'id': 12345},
                )

    def test_direct_extra(self):
        e = self.session.parse_user_input('Version:12345?code=Something')
        self.assertSameEntity(e, {'type': 'Version', 'id': 12345})
        self.assertEqual(e.get('code'), 'Something')
