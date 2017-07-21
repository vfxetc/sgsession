from common import *

from sgschema import Schema


class TestDirMap(TestCase):
    
    def test_basics(self):

        session = Session(dir_map='/src:/dst')
        x = session.merge({'type': 'Version', 'sg_path_to_movie': '/src/movie.mp4'})
        self.assertEqual(x['sg_path_to_movie'], '/dst/movie.mp4')

        