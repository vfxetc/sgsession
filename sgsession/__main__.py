import sys

from shotgun_api3_registry import connect as _connect

from . import Session

sg = Session(_connect())


if len(sys.argv) >= 3:
    entity = sg.get(sys.argv[1], int(sys.argv[2]), fields=sys.argv[3:])
    entity.pprint()
