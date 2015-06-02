from shotgun_api3_registry import connect as _connect

from . import Session

sg = Session(_connect())
