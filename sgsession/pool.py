"""A wrapper around ``shotgun_api3`` to allow for parallel requests.

The standard Shotgun API uses a connection object that serialized requests.
Therefore, efficient usage in a multi-threaded environment is tricker than it
could be. Ergo, this module was concieved.

:class:`ShotgunPool` is a connection pool that creates fresh Shotgun instances
when needed, and recycles old ones after use. It proxies attributes and
methods to the managed instances. An actual Shotgun instance should never leak
out of this object, so even passing around bound methods from this object
should be safe.

E.g.::

    >>> # Construct and wrap a Shotgun instance.
    >>> shotgun = Shotgun(...)
    >>> shotgun = ShotgunPool(shotgun)
    >>>
    >>> # Use it like normal, except in parallel.
    >>> shotgun.find('Task', ...)

"""

from __future__ import absolute_import

from threading import local
import functools
import types
import contextlib

from shotgun_api3 import Shotgun


class ShotgunPool(object):

    """Shotgun connection pool.

    :param prototype: Shotgun instance to use as a prototype, OR the
        ``base_url`` to be used to construct a prototype.

    If passed a ``base_url``, the remaining args and kwargs will be passed to
    the Shotgun constructor for creation of a prototype.

    The ``config`` object of the prototype will be shared amoung all Shotgun
    instances created; changing the settings on one Shotgun instance (or this
    object) will affect all other instances.

    """

    def __init__(self, prototype, *args, **kwargs):

        self._free_instances = []

        # Construct a prototype Shotgun if we aren't given one.
        if not isinstance(prototype, Shotgun):
            kwargs.setdefault('connect', False)
            prototype = Shotgun(prototype, *args, **kwargs)
        self._prototype = prototype

        # Remember stuff to apply onto real instances.
        self.base_url = prototype.base_url
        self.config = prototype.config

    def _create_instance(self):
        instance = Shotgun(self.base_url, 'dummy_script_name', 'dummy_api_key', connect=False)
        instance.config = self.config
        return instance

    def _acquire_instance(self):
        try:
            return self._free_instances.pop(0)
        except IndexError:
            pass
        return self._create_instance()

    def _release_instance(self, instance):
        self._free_instances.append(instance)

    @contextlib.contextmanager
    def _context(self):
        instance = self._acquire_instance()
        try:
            yield instance
        finally:
            self._release_instance(instance)

    @classmethod
    def _add_local_attr(cls, name):

        def getter(self):
            with self._context() as instance:
                return getattr(instance, name)

        def setter(self, value):
            with self._context() as instance:
                setattr(instance, name, value)

        getter.__name__ = name
        setattr(cls, name, property(getter, setter))

    @classmethod
    def _add_local_method(cls, name):

        existing = getattr(Shotgun, name)

        @functools.wraps(existing)
        def method(self, *args, **kwargs):
            with self._context() as instance:
                return existing(instance, *args, **kwargs)

        setattr(cls, name, method)


# Register the attributes we want to proxy.
for name in ('client_caps', 'server_caps'):
    ShotgunPool._add_local_attr(name)

# Register all public methods.
for name, value in Shotgun.__dict__.iteritems():
    if not name.startswith('_') and isinstance(value, types.FunctionType):
        ShotgunPool._add_local_method(name)

