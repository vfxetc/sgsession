from __future__ import absolute_import

from threading import local
import functools
import types

from shotgun_api3 import Shotgun


class LocalShotgun(object):

    def __init__(self, prototype, *args, **kwargs):

        self._locals = local()

        # Construct a prototype Shotgun if we aren't given one.
        if not isinstance(prototype, Shotgun):
            kwargs.setdefault('connect', False)
            prototype = Shotgun(prototype, *args, **kwargs)
        self._prototype = prototype

        # Remember stuff to apply onto real instances.
        self.base_url = prototype.base_url
        self.config = prototype.config

    def _local_instance(self, create=True):

        try:
            return getattr(self._locals, 'instance')
        except AttributeError:
            if create:
                # Create a new object, and share our config with it.
                instance = Shotgun(self.base_url, 'dummy_script_name', 'dummy_api_key')
                instance.config = self.config
                setattr(self._locals, 'instance', instance)
                return instance

    @classmethod
    def _add_local_attr(cls, name):

        def getter(self):
            return getattr(self._local_instance(), name)

        def setter(self, value):
            setattr(self._local_instance(), name, value)

        getter.__name__ = name
        setattr(cls, name, property(getter, setter))

    @classmethod
    def _add_local_method(cls, name):

        existing = getattr(Shotgun, name)

        @functools.wraps(existing)
        def method(self, *args, **kwargs):
            return existing(self._local_instance(), *args, **kwargs)

        setattr(cls, name, method)


# Register the attributes we want to proxy.
for name in ('client_caps', 'server_caps'):
    LocalShotgun._add_local_attr(name)

# Register all public methods.
for name, value in Shotgun.__dict__.iteritems():
    if not name.startswith('_') and isinstance(value, types.FunctionType):
        LocalShotgun._add_local_method(name)

