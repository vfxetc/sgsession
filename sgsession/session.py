"""The Session is a wrapper around a Shotgun instance, proxying requests to
the server and applying additional logic on top of it. The Session instance is
designed to be used for a single task and then discarded, since it makes the
assumption that entity relationships do not change.

While not fully documented below, this object will proxy all attributes to the
underlying Shotgun instance, so you can treat this as you would a Shotgun
instance.

"""

from __future__ import with_statement, absolute_import

import errno
import functools
import itertools
import json
import logging
import os
import re
import threading
import urlparse
import warnings

from sgschema import Schema
from dirmap import DirMap

from .entity import Entity
from .pool import ShotgunPool
from .utils import expand_braces, parse_isotime, shotgun_api3_connect, cached_property



log = logging.getLogger(__name__)


class EntityNotFoundWarning(UserWarning):
    pass

class EntityNotFoundError(ValueError):
    pass


def _asyncable(func):
    """Wrap a function, so that async=True will run it in a thread."""
    @functools.wraps(func)
    def _wrapped(self, *args, **kwargs):
        if kwargs.pop('async', False):
            return self._submit_concurrent(func, self, *args, **kwargs)
        else:
            return func(self, *args, **kwargs)
    return _wrapped

def _assert_ownership(func):
    """Wrap a function that takes a list of entities, and make sure that we own them."""
    @functools.wraps(func)
    def _wrapped(self, entities, *args, **kwargs):
        entities = list(entities)
        for e in entities:
            if isinstance(e, Entity):
                if e.session is not self:
                    raise ValueError('Entity not from this session', e, self)
            else:
                raise TypeError('Non-Entity passed as entity', e)
        return func(self, entities, *args, **kwargs)
    return _wrapped


_recursion_sentinel = object()


class Session(object):
    
    """Shotgun wrapper.

    :param shotgun: A Shotgun instance to wrap, or the name to be passed to
        ``shotgun_api3_registry.connect()`` in order to construct one.

    If passed a name, the remaining args and kwargs will also be passed to the
    api registry connector.

    If passed a descendant of ``shotgun_api3.Shotgun`` (or one is constructed
    via the registry), it will be wrapped in a :class:`~sgsession.pool.ShotgunPool` so that
    it becomes thread-safe. Any other objects (e.g. mock servers) are used
    unmodified.

    If passed nothing, ``shotgun_api3_registry.connect`` will be called
    the first time :attr:`shotgun` is accessed (which will happen on many
    operations). To stop this behaviour, pass ``False``.

    """
    
    #: Mapping of entity types to the field where their "parent" lives.
    parent_fields = {
        'Asset': 'project',
        'Project': None,
        'Sequence': 'project',
        'Shot': 'sg_sequence',
        'Task': 'entity',
        'PublishEvent': 'sg_link',
        'Version': 'entity',

        # Lofty Sky custom entities.
        # Please complain loudly if they affects your studio, because I have
        # a plan to do this better.
        'CustomEntity06': 'project', # $Book
        'CustomEntity04': 'sg_book', # $BookIssue
        'CustomEntity21': 'sg_issue', # $BookPage

    }
    
    #: Fields to always fetch for every entity.
    important_fields_for_all = ['updated_at']
    
    #: Fields to always fetch: maps entity type to a list of fields.
    important_fields = {
        'Asset': ['code', 'sg_asset_type'],
        'HumanUser': ['firstname', 'lastname', 'email', 'login'],
        'Project': ['name'],
        'PublishEvent': ['code', 'sg_type', 'sg_version'],
        'Sequence': ['code'],
        'Shot': ['code'],
        'Step': ['code', 'short_name', 'entity_type'],
        'Task': ['step', 'content'],
        'Version': ['code', 'sg_task'],

        # Lofty Sky custom entities.
        'CustomEntity06': ['code'], # $Book
        'CustomEntity04': ['code'], # $BookIssue
        'CustomEntity21': ['code'], # $BookPage
    }
    
    #: Links to always fetch: maps entity type to a mapping of field names to
    #: a list of their potential entity types.
    important_links = {
        'Asset': {
            'project': ['Project'],
        },
        'Sequence': {
            'project': ['Project'],
        },
        'Shot': {
            'project': ['Project'],
            'sg_sequence': ['Sequence'],
        },
        'Task': {
            'project': ['Project'],
            'entity': ['Asset', 'Shot'],
            'step': ['Step'],
        },
        'PublishEvent': {
            'project': ['Project'],
            'sg_link': ['Task'],
        },
    }
    
    def __init__(self, shotgun=None, schema=None, dir_map=None, **kwargs):

        # Lookup strings in the script registry.
        if isinstance(shotgun, basestring):
            shotgun = shotgun_api3_connect(shotgun, **kwargs)

        # Wrap basic shotgun instances in our threader.
        self._shotgun = ShotgunPool.wrap(shotgun)
        self._shotgun_kwargs = None if shotgun else kwargs

        self._schema = schema
        self._dir_map = dir_map

        self._cache = {}
        self._thread_pool = None
    
    @classmethod
    def from_entity(cls, entity, *args, **kwargs):
        if isinstance(entity, Entity) and entity.session:
            return entity.session
        else:
            return cls(*args, **kwargs)

    @property
    def shotgun(self):
        # Automatically generate Shotgun when we need one.
        # We use False to track that there should be nothing set here.
        if self._shotgun is None:
            self._shotgun = ShotgunPool.wrap(shotgun_api3_connect(
                **self._shotgun_kwargs
            )) or False
        return self._shotgun

    @property
    def schema(self):
        # Automaticaly load schema when we need one.
        # We use False to track that there should be nothing set here.
        if self._schema is None:

            # Wait on caching a schema here until there is a Shotgun.
            shotgun = self.shotgun
            if not shotgun:
                return

            try:
                self._schema = Schema.from_cache(shotgun)
            except ValueError:
                self._schema = False

        return self._schema or None

    @cached_property
    def dir_map(self):
        return DirMap(self._dir_map or os.environ.get('SGSESSION_DIR_MAP'))

    def __getattr__(self, name):
        return getattr(self.shotgun, name)
    
    def __reduce__(self):
        # We assume that the shotgun and sgcache will automatically regenerate.
        # Generally, the user should be very careful when pickling sessions.
        shotgun = False if self._shotgun is False else None
        schema = False if self._schema is False else None
        return self.__class__, (shotgun, schema)

    def merge(self, data, over=None, created_at=None, _depth=0, _memo=None):
        """Import data containing raw entities into the session.
        
        This will effectively return a copy of any nested structure of lists,
        tuples, and dicts, while converting any dicts which look like entities
        into an :class:`.Entity`. The returned structure is a copy of the
        original.
        
        :param dict data: The raw fields to convert into an :class:`~sgsession.entity.Entity`.
        :param bool over: Control for merge behaviour with existing data.
            ``True`` results in the new data taking precedence, and ``False``
            the old data. The default of ``None`` will automatically decide
            based on the ``updated_at`` field.
        
        :return: The :class:`~sgsession.entity.Entity`. This will not be a new instance if the
            entity was already in the session, but it will have all the newly
            merged data in it.
        
        """

        # Track down where we are getting string created_at from.
        if created_at and isinstance(created_at, basestring):
            # This can be a huge message...
            log.error('string created_at (%r) given to Session.merge at depth %d; data to merge: %r' % (
                created_at, _depth, data,
            ))
            created_at = parse_isotime(created_at)

        # Since we are dealing with recursive structures, we need to memoize
        # the outputs by all of the inputs as we create them.
        if _memo is None:
            _memo = {}
        id_ = id(data)
        if id_ in _memo:
            return _memo[id_]

        _memo[id_] = _recursion_sentinel
        obj = self._merge(data, over, created_at, _depth, _memo)

        # If something fails at setting up a recursive object before returning,
        # then we want to fail very hard.
        if obj is _recursion_sentinel:
            raise RuntimeError('un-memoized recursion')

        _memo[id_] = obj
        return obj

    def _merge(self, data, over, created_at, depth, memo):

        # No need to worry about resolving schema here, since Entity.__setitem__
        # will ultimately do it.

        # Pass through entities if they are owned by us.
        if isinstance(data, Entity) and data.session is self:
            return data
        
        # Contents of lists and tuples should get merged.
        if isinstance(data, list):
            # Lists can be cyclic; memoize them.
            memo[id(data)] = new = type(data)()
            new.extend(self.merge(x, over, created_at, depth + 1, memo) for x in data)
            return new
        if isinstance(data, tuple):
            return type(data)(self.merge(x, over, created_at, depth + 1, memo) for x in data)
        
        if isinstance(data, basestring):
            return self.dir_map(data)

        if not isinstance(data, dict):
            return data
        
        # Non-entity dicts have all their values merged.
        if not ('type' in data and 'id' in data):
            memo[id(data)] = new = type(data)() # Setup recursion block.
            new.update((k, self.merge(v, over, created_at)) for k, v in data.iteritems())
            return new

        # If it already exists, then merge this into the old one.
        new = Entity(data['type'], data['id'], self)
        key = new.cache_key
        entity = self._cache.setdefault(new.cache_key, new)
        memo[id(data)] = entity # Setup recursion block.
        entity._update(data, over, created_at, depth + 1, memo)
        return entity
    
    def parse_user_input(self, spec, entity_types=None, fetch_project_from_page=False):
        """Parse user input into an entity.

        :param str spec: The string of input from the user.
        :param tuple entity_types: Acceptable entity types. Effective against
            paths.
        :param bool fetch_project_from_page: Allow pulling projects from the
            more abstract pages.
        :return: :class:`.Entity` or ``None``.

        Acceptable forms of input are:

        - Type-ID tuples, e.g. ``Task:123``, or ``Task_123``; accepts arbitrary
          URL-like fields, e.g. ``Task:123?code=Example``.
        - JSON, e.g. ``{"type": "Task", "id", 123}``
        - Bare IDs, e.g. ``123``; only if ``entity_types`` is provided.
        - Shotgun URLs including the entity, e.g. ``https://example.shotgunstudio.com/detail/Task/123`` or
          ``https://example.shotgunstudio.com/page/999#Task_123_Example``
        - Shotgun pages without an entity, e.g. ``https://example.shotgunstudio.com/page/999``,
          which describes ``Task 123``; only when ``fetch_project_from_page``.

        Example::

            >>> sg.parse_user_input('Task:123')
            <Entity Task:123 at 0x110863618>

        """

        spec = spec.strip()

        # JSON.
        if spec.startswith('{') and spec.endswith('}'):
            raw = json.loads(spec)
            if 'type' not in raw or 'id' not in raw:
                raise ValueError('incomplete JSON entity', spec)
            if not isinstance(raw['type'], basestring) or not isinstance(raw['id'], int):
                raise ValueError('malformed JSON entity', spec)
            return self.merge(raw)

        # Accept integer IDs if we know we want a specific type.
        if spec.isdigit():
            if isinstance(entity_types, basestring):
                entity_types = [entity_types]
            if entity_types and len(entity_types) == 1:
                return self.merge({'type': entity_types[0], 'id': int(spec)})
            else:
                raise ValueError('int-only spec without single entity_types', spec, entity_types)
            
        # Shotgun detail URL.
        m = re.match(r'^https?://\w+\.shotgunstudio\.com/detail/([A-Za-z]+\d*)/(\d+)', spec)
        if m:
            return self.merge({'type': m.group(1), 'id': int(m.group(2))})

        # Shotgun project overview URL.
        m = re.match(r'^https?://\w+\.shotgunstudio\.com/page/\d+#([A-Z][A-Za-z]+\d*)_(\d+)_', spec)
        if m:
            return self.merge({'type': m.group(1), 'id': int(m.group(2))})
        
        # Shotgun page URL.
        m = re.match(r'^https?://\w+\.shotgunstudio\.com/page/(\d+)$', spec)
        if m:
            if not fetch_project_from_page:
                raise ValueError('page URL without fetch_project_from_page', spec)
            page = self.get('Page', int(m.group(1)), ['project'])
            if not page:
                raise ValueError('Page entity not found for page URL', spec)
            if page.get('project'):
                return self.merge(page['project'])
            raise ValueError('page URL has no project', spec)
            
        # Direct entities. E.g. `shot:12345?code=whatever`
        m = re.match(r'^([A-Za-z]{3,}\d*)[:_ -](\d+)(?:_|$|\?(\S*))', spec)
        if m:
            type_, id_, query = m.groups()
            raw = {
                'type': type_[0].upper() + type_[1:],
                'id': int(id_),
            }
            if query:
                for k, v in urlparse.parse_qsl(query, keep_blank_values=True):
                    raw.setdefault(k, v)
            return self.merge(raw)
        
        raise ValueError('could not parse entity spec', spec)

    def _submit_concurrent(self, func, *args, **kwargs):
        if not self._thread_pool:
            from concurrent.futures import ThreadPoolExecutor
            self._thread_pool = ThreadPoolExecutor(8)
        return self._thread_pool.submit(func, *args, **kwargs)

    @_asyncable
    def create(self, type, data=None, return_fields=None, **kwargs):
        """Create an entity of the given type and data.
        
        :return: The new :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-create>`_
        
        """
        if data is not None and kwargs:
            # This isn't quite ideal, but it doesn't let must confusing get through.
            raise TypeError('provide only one of data or **kwargs')
        data = self._minimize_entities(data if data is not None else kwargs)
        if self.schema:
            type = self.schema.resolve_one_entity(type)
            data = self.schema.resolve_structure(data, type)
            return_fields = self.schema.resolve_field(type, return_fields) if return_fields else []
        return_fields = self._add_default_fields(type, return_fields)
        return self.merge(self.shotgun.create(type, data, return_fields))

    @_asyncable
    def update(self, *args, **kwargs):
        """Update the given entity with the given fields.
        
        .. todo:: Add this to the Entity.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-update>`_
        
        """

        # Grab the "type" or 1st argument.
        if not (args or kwargs):
            raise TypeError('no arguments')
        type_ = kwargs.pop('type', None)
        if type_ is None:
            if not args:
                raise TypeError('must provide "type" kwarg or positional type argument')
            type_ = args[0]
            args = args[1:]

        # Figure out if we were given an Entity, or an entity type (string)
        if isinstance(type_, Entity):
            ids = [type_['id']]
            type_ = type_['type']
            do_batch = False
        elif isinstance(type_, basestring):
            ids = kwargs.pop('id', None) or args[0]
            args = args[1:]
            do_batch = not isinstance(ids, int)
            ids = list(ids) if do_batch else [ids]
        elif isinstance(type_, (list, type)):
            do_batch = True
            entities = list(type_)
            if not entities:
                raise ValueError('entity sequence is empty')
            sentinel = object()
            non_entity = next((e for e in entities if not isinstance(e, Entity)), sentinel)
            if non_entity is not sentinel:
                raise ValueError('entity sequence contains non-Entity', non_entity)
            type_ = entities[0]['type']
            mismatched = next((e for e in entities if e['type'] != type_), None)
            if mismatched is not None:
                raise ValueError('mismatched entity types', type_, mismatched['type'])
            ids = [e['id'] for e in entities]
        else:
            raise TypeError('first argument must be an Entity, list of entities, or string (entity type)', entity_or_type)

        data = {}
        for arg in args:
            data.update(arg)
        data.update(kwargs)
        if not data:
            raise ValueError('no data provided')
        data = self._minimize_entities(data)
        if self.schema:
            type_ = self.schema.resolve_one_entity(type_)
            data = self.schema.resolve_structure(data, type_)

        if do_batch:
            return self.batch([{
                'request_type': 'update',
                'entity_type': type_,
                'entity_id': id_,
                'data': data,
            } for id_ in ids])
        else:
            return self.merge(self.shotgun.update(type_, ids[0], data), over=True)

    @_asyncable
    def batch(self, requests):
        """Perform a series of requests in a transaction.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-batch>`_
        
        """
        requests = self._minimize_entities(requests)
        if self.schema:
            requests = self.schema.resolve_structure(requests)
        return [self.merge(x, over=True) if isinstance(x, dict) else x for x in self.shotgun.batch(requests)]
    
    def _add_default_fields(self, type_, fields):
        
        fields = set(fields or ['id'])
        
        # Add important fields for this type.
        fields.update(self.important_fields_for_all)
        fields.update(self.important_fields.get(type_, []))
        
        # Add parent.
        parent_field = self.parent_fields.get(type_)
        if parent_field:
            fields.add(parent_field)
        
        # Add implied owners of deep-fields.
        implied = set()
        for field in fields:
            parts = field.split('.')
            for i in xrange(2, len(parts) + 1, 2):
                implied.add('.'.join(parts[:i]) + '.id')
        fields.update(implied)

        # Add important deep-fields for requested type.
        for local_field, link_types in self.important_links.get(type_, {}).iteritems():
            fields.add(local_field)
            for link_type in link_types:
                remote_fields = self.important_fields.get(link_type, [])
                remote_links = self.important_links.get(link_type, {})
                for remote_field in itertools.chain(self.important_fields_for_all, remote_fields, remote_links.iterkeys()):
                    fields.add('%s.%s.%s' % (local_field, link_type, remote_field))
        
        return sorted(fields)
    
    def _minimize_entities(self, data):
        
        if isinstance(data, dict):

            # Attachments need to not be minimized, since they are often
            # merged in with their own metadata. If we special cased merging
            # them, then this could be a bit smarter and send only what is
            # nessesary.
            if data.get('type') == 'Attachment':
                return data

            if 'type' in data and 'id' in data:
                return dict(type=data['type'], id=data['id'])

            return dict((k, self._minimize_entities(v)) for k, v in data.iteritems())

        if isinstance(data, (list, tuple)):
            return [self._minimize_entities(x) for x in data]

        return data
    
    @_asyncable
    def find(self, type_, filters, fields=None, *args, **kwargs):
        """Find entities.
        
        :return: :class:`list` of found :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-find>`_
        
        """

        merge = kwargs.pop('merge', True)

        if self.schema:
            type_ = self.schema.resolve_one_entity(type_)

        if kwargs.pop('add_default_fields', True):
            fields = self._add_default_fields(type_, fields)

        # Expand braces in fields.
        expanded_fields = set()
        for field in fields:
            expanded_fields.update(expand_braces(field))
        fields = sorted(expanded_fields)

        # Resolve names in fields.
        if self.schema:
            filters = self.schema.resolve_structure(filters)
            fields = self.schema.resolve_field(type_, fields) if fields else []

        filters = self._minimize_entities(filters)

        # Resolve names in filters.
        if self.schema and isinstance(filters, (list, tuple)):
            for i, old_filter in enumerate(filters):
                filter_ = [self.schema.resolve_one_field(type_, old_filter[0])]
                filter_.extend(old_filter[1:])
                filters[i] = filter_

        result = self.shotgun.find(type_, filters, fields, *args, **kwargs)

        return [self.merge(x, over=True) for x in result] if merge else result
    
    @_asyncable
    def find_one(self, entity_type, filters, fields=None, order=None,
        filter_operator=None, retired_only=False, **kwargs):
        """Find one entity.
        
        :return: :class:`~sgsession.entity.Entity` or ``None``.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-find_one>`_
        
        """
        results = self.find(entity_type, filters, fields, order,
            filter_operator, 1, retired_only, **kwargs)
        if results:
            return results[0]
        return None
    
    def find_iter(self, *args, **kwargs):

        limit = kwargs.pop('limit', None) or None
        per_page = kwargs.pop('per_page', limit or 500) # this is the default
        async_count = kwargs.pop('async_count', 1)

        kwargs['limit'] = per_page
        kwargs['async'] = True

        page = 1
        futures = []
        done = False

        while not done:

            # extract all complete results; we wait for the first one, but
            # then take as many others as are already done
            rows = futures.pop(0).result() if futures else None
            while rows and futures and futures[0].done():
                rows.extend(futures.pop(0).result())

            # determine if we are done yet
            if rows is not None:
                # print 'got', len(rows)
                # we hit the end of results
                if not rows or len(rows) < per_page:
                    done = True
                # we hit the total requested
                if limit is not None:
                    limit -= len(rows)
                    if limit <= 0:
                        done = True

            # queue up the next queries
            while not done and len(futures) < async_count:
                # print 'queing', page
                kwargs['page'] = page
                futures.append(self.find(*args, **kwargs))
                page += 1

            # yield results
            if rows is not None:
                for x in rows:
                    yield x




    @_asyncable
    def delete(self, entity, entity_id=None):
        """Delete one entity.
        
        .. warning:: This session will **not** forget about the deleted entity,
            and all links from other entities will remain intact.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-delete>`_
        
        """

        if not isinstance(entity, Entity):
            if self.schema:
                entity = self.schema.resolve_one_entity(entity)
            if not entity_id:
                raise ValueError('must provide entity_id')
            entity = self.merge({'type': entity, 'id': entity_id})

        res = self.shotgun.delete(entity['type'], entity['id'])
        entity._exists = False

        return res
        
    @_asyncable
    def get(self, type_, id_, fields=None, fetch=True):
        """Get one entity by type and ID.
        
        :param str type_: The entity type to lookup.
        :param int id_: The entity ID to lookup. Accepts ``list`` or ``tuple``
            of IDs, and returns the same.
        :param bool fetch: Request this entity from the server if not cached?
        
        """

        # Handle multiple IDs.
        if isinstance(id_, (list, tuple)):
            return type(id_)(self.get(type_, x) for x in id_)

        if self.schema:
            type_ = self.schema.resolve_one_entity(type_)

        try:
            entity = self._cache[(type_, id_)]
        except KeyError:
            return self.find_one(type_, [('id', 'is', id_)], fields or [])
        else:
            if fetch and fields:
                entity.fetch(fields)
            return entity
    
    def get_url(self, url):
        """Get one entity by it's URL on Shotgun.

        :param str url: The url to parse.

        """

        # Shotgun detail URL.
        m = re.match(r'^https?://\w+\.shotgunstudio\.com/detail/([A-Za-z]+)/(\d+)', url)
        if m:
            return self.get(m.group(1).title(), int(m.group(2)))
    
        # Shotgun project overview URL.
        m = re.match(r'^https?://\w+\.shotgunstudio\.com/page/\d+#([A-Z][A-Za-z]+)_(\d+)_', url)
        if m:
            return self.get(m.group(1).title(), int(m.group(2)))
        
        raise ValueError('cannot parse url: %r' % url)

    def _fetch(self, entities, fields, force=False):
        
        types = list(set(x['type'] for x in entities))
        if len(types) > 1:
            raise ValueError('can only fetch one type at once')
        type_ = types[0]
        
        ids_ = set()
        for e in entities:
            if force or any(f not in e for f in fields):
                ids_.add(e['id'])
        if ids_:
            res = self.find(
                type_,
                [['id', 'in'] + list(ids_)],
                fields,
            )
            missing = ids_.difference(e['id'] for e in res)

            # Update _exists on the entities.
            for e in entities:
                e._exists = e['id'] not in missing

            if missing:
                raise EntityNotFoundError('%s %s not found' % (type_, ', '.join(map(str, sorted(missing)))))

    @_assert_ownership
    @_asyncable
    def filter_exists(self, entities, check=True, force=False):
        """Return the subset of given entities which exist (non-retired).

        :param list entities: An iterable of entities to check.
        :param bool check: Should the server be consulted if we don't already know?
        :param bool force: Should we always check the server?
        :returns set: The entities which exist, or aren't sure about.

        This will handle multiple entity-types in multiple requests.

        """

        if check:

            by_type = {}
            for x in entities:
                by_type.setdefault(x['type'], set()).add(x)
            for type_, sub_entities in by_type.iteritems():

                if force or any(e._exists is None for e in sub_entities):
                    found = self.find(type_, [['id', 'in'] + list(e['id'] for e in sub_entities)])
                    found_ids = set(e['id'] for e in found)
                    for e in sub_entities:
                        e._exists = e['id'] in found_ids

        return set(e for e in entities if (e._exists or e._exists is None))

    @_assert_ownership
    @_asyncable
    def fetch(self, to_fetch, fields, force=False):
        """Fetch the named fields on the given entities.
        
        :param list to_fetch: Entities to fetch fields for.
        :param list fields: The names of fields to fetch on those entities.
        :param bool force: Perform a request even if we already have this data?
        
        This will safely handle multiple entitiy types at the same time, and
        by default will only make requests of the server if some of the data
        does not already exist.
        
        .. note:: This does not assert that all "important" fields exist. See
            :meth:`fetch_core`.
        
        """
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self._fetch(entities, fields, force=force)
    
    @_assert_ownership
    @_asyncable
    def fetch_backrefs(self, to_fetch, backref_type, field):
        """Fetch requested backrefs on the given entities.
        
        :param list to_fetch: Entities to get backrefs on.
        :param str backref_type: The entity type to look for backrefs on.
        :param str field: The name of the field to look for backrefs in.
        
        ::
            
            # Find all tasks which refer to this shot.
            >>> session.fetch_backrefs([shot], 'Task', 'entity')
            
        """
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self.find(backref_type, [[field, 'is'] + [x.minimal for x in entities]])

    @_assert_ownership
    @_asyncable
    def fetch_core(self, to_fetch):
        """Assert all "important" fields exist, and fetch them if they do not.
        
        :param list to_fetch: The entities to get the core fields on.
        
        This will populate all important fields, and important fields on linked
            entities.
        
        """
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self._fetch(entities, itertools.chain(
                self.important_fields_for_all,
                self.important_fields.get(type_) or (),
                self.important_links.get(type_, {}).iterkeys(),
            ))
            
    @_assert_ownership
    @_asyncable
    def fetch_heirarchy(self, to_fetch):
        """Populate the parents as far up as we can go, and return all involved.
        
        With (new-ish) arbitrarily-deep-links on Shotgun, this method could be
        made quite a bit more effiecient, since it should be able to request
        the entire heirarchy for any given type at once.

        See :attr:`parent_fields`.
        
        """

        all_nodes = set()
        to_resolve = set()
        loop_count = 0

        while to_fetch or to_resolve:

            # Just in case (because we have messed this up a few times before).
            if loop_count > 20:
                raise RuntimeError('likely infinite loop')
            loop_count += 1

            # Go as far up as we already have for the specified entities.
            for entity in to_fetch:
                all_nodes.add(entity)
                while entity.parent(fetch=False):
                    entity = entity.parent()
                    all_nodes.add(entity)
                if entity['type'] != 'Project':
                    to_resolve.add(entity)
            
            # There is nothing new to fetch; bail!
            if not to_resolve:
                break
            
            # Find the type that we have the most entities of, and remove them
            # from the list to resolve.
            by_type = {}
            for x in to_resolve:
                all_nodes.add(x)
                by_type.setdefault(x['type'], set()).add(x)
            type_, to_fetch = max(by_type.iteritems(), key=lambda x: len(x[1]))
            to_resolve.difference_update(to_fetch)
            
            # Fetch the parent names.
            ids = [x['id'] for x in to_fetch]
            parent_name = self.parent_fields[type_]
            found = self.find(type_, [['id', 'in'] + ids], [parent_name])

            # Make sure we actually get something back for the parent field.
            no_parent = [e['id'] for e in found if not e.get(parent_name)]
            if no_parent:
                raise ValueError('%s %s %s no %s' % (
                    type_,
                    ', '.join(str(id_) for id_ in sorted(no_parent)),
                    'have' if len(no_parent) > 1 else 'has',
                    parent_name,
                ))

            # Track those which didn't come back from the API. Normally, this
            # wouldn't happen, but can result from a race condition OR from
            # an error on the server side (or a caching layer).
            missing = to_fetch.difference(found)
            if missing:
                raise EntityNotFoundError('%s %s %s not exist' % (
                    type_,
                    ', '.join(str(id_) for id_ in sorted(no_parent)),
                    'do' if len(missing) > 1 else 'does',
                ))
        
        return list(all_nodes)
    
    _guessed_user_lock = threading.Lock()
    
    @_asyncable
    def guess_user(self, filter=('email', 'starts_with', '{login}@'), fields=(), fetch=True):
        """Guess Shotgun user from current login name.
        
        Looks for $SHOTGUN_USER_ID in your environment, then a user with an
        email that has the login name as the account.
    
        :returns: ``dict`` of ``HumanUser``, or ``None``.
    
        """
        with self._guessed_user_lock:

            try:
                user = self._guessed_user
            except AttributeError:
                user = self._guess_user(filter, fields, fetch)
                if user:
                    Session._guessed_user = self.merge(user).as_dict()
                else:
                    Session._guessed_user = None

            if not user:
                return
            entity = self.merge(user)
            if fields:
                entity.fetch(fields)
            return entity


    def _guess_user(self, filter, fields, fetch):

        # This envvar is used only for this purpose (at Western Post)
        id_ = os.environ.get('SHOTGUN_USER_ID')
        if id_:
            return {'type': 'HumanUser', 'id': int(id_)}

        if not fetch:
            return

        # This envvar is more general, and respected by shotgun_api3_registry.
        login = os.environ.get('SHOTGUN_SUDO_AS_LOGIN')
        if login:
            return self.find_one('HumanUser', [
                ('login', 'is', login),
            ], fields or ())

        # Finally, search for a user based on the current login.
        try:
            login = os.getlogin()
        except OSError as e:
            # this fails on the farm, so fall back onto the envvar
            if e.errno != errno.ENOTTY:
                raise
            login = os.environ.get('USER')

        filter_ = tuple(x.format(login=login) for x in filter)
        return self.find_one('HumanUser', [filter_], fields)
