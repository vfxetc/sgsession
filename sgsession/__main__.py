import sys

from . import Session

sg = Session()


if len(sys.argv) >= 3:
    entity = sg.get(sys.argv[1], int(sys.argv[2]), fields=sys.argv[3:])
    entity.pprint()
