"""The Session is a wrapper around a Shotgun instance, proxying requests to
the server and applying additional logic on top of it. The Session instance is
designed to be used for a single task and then discarded, since it makes the
assumption that entity relationships do not change.

While not fully documented below, this object will proxy all attributes to the
underlying Shotgun instance, so you can treat this as you would a Shotgun
instance.

"""

from __future__ import with_statement, absolute_import

import itertools
import os
import threading
import warnings

from shotgun_api3 import Shotgun as _BaseShotgun

from .entity import Entity
from .pool import ShotgunPool

class EntityNotFoundWarning(UserWarning):
    pass


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
    
    def __init__(self, shotgun=None, *args, **kwargs):

        # Lookup strings in the script registry.
        if isinstance(shotgun, basestring):
            import shotgun_api3_registry
            shotgun = shotgun_api3_registry.connect(shotgun, *args, **kwargs)

        # Wrap basic shotgun instances in our threader.
        if isinstance(shotgun, _BaseShotgun):
            shotgun = ShotgunPool(shotgun)

        self.shotgun = shotgun
        self._cache = {}
    
    def __getattr__(self, name):
        return getattr(self.shotgun, name)
    
    def merge(self, data, over=None, created_at=None):
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
        
        # Pass through entities if they are owned by us.
        if isinstance(data, Entity):
            if data.session is not self:
                raise ValueError('entity not owned by this session')
            return data
        
        # Contents of lists and tuples should get merged.
        if isinstance(data, (list, tuple)):
            # Assuming that the real type can take reconstruction...
            return type(data)(self.merge(x, over, created_at) for x in data)
        
        if not isinstance(data, dict):
            return data
        
        # Non-entity dicts have all their values merged.
        if not ('type' in data and 'id' in data):
            return dict((k, self.merge(v, over, created_at)) for k, v in data.iteritems())

        # If it already exists, then merge this into the old one.
        new = Entity(data['type'], data['id'], self)
        key = new.cache_key
        if key in self._cache:
            entity = self._cache[key]
            entity._update(entity, data, over, created_at)
            return entity
        
        # Return the new one.
        self._cache[key] = new
        new._update(new, data, over, created_at)
        return new
    
    def create(self, type_, data, return_fields=None):
        """Create an entity of the given type and data.
        
        :return: The new :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-create>`_
        
        """
        data = self._minimize_entities(data)
        return_fields = self._add_default_fields(type_, return_fields)
        return self.merge(self.shotgun.create(type_, data, return_fields))

    def update(self, type_, id, data):
        """Update the given entity with the given fields.
        
        .. todo:: Add this to the Entity.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-update>`_
        
        """
        data = self._minimize_entities(data)
        return self.merge(self.shotgun.update(type_, id, data), over=True)

    def batch(self, requests):
        """Perform a series of requests in a transaction.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-batch>`_
        
        """
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
            parts = field.split('.', 2)
            if len(parts) > 1:
                implied.add('.'.join(parts[:2]) + '.id')
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
            if 'type' in data and 'id' in data:
                return dict(type=data['type'], id=data['id'])
            return dict((k, self._minimize_entities(v)) for k, v in data.iteritems())
        if isinstance(data, (list, tuple)):
            return [self._minimize_entities(x) for x in data]
        return data
        
    def find(self, type_, filters, fields=None, *args, **kwargs):
        """Find entities.
        
        :return: :class:`list` of found :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-find>`_
        
        """
        
        fields = self._add_default_fields(type_, fields)
        filters = self._minimize_entities(filters)
        result = self.shotgun.find(type_, filters, fields, *args, **kwargs)
        return [self.merge(x, over=True) for x in result]
        
    
    def find_one(self, entity_type, filters, fields=None, order=None, 
        filter_operator=None, retired_only=False):
        """Find one entity.
        
        :return: :class:`~sgsession.entity.Entity` or ``None``.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-find_one>`_
        
        """
        results = self.find(entity_type, filters, fields, order, 
            filter_operator, 1, retired_only)
        if results:
            return results[0]
        return None
    
    def delete(self, entity, entity_id=None):
        """Delete one entity.
        
        .. warning:: This session will **not** forget about the deleted entity,
            and all links from other entities will remain intact.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-delete>`_
        
        """

        if not isinstance(entity, Entity):
            if not entity_id:
                raise ValueError('must provide entity_id')
            entity = self.merge({'type': entity, 'id': entity_id})

        res = self.shotgun.delete(entity['type'], entity['id'])
        entity._exists = False

        return res
        
    def get(self, type_, id_, fetch=True):
        """Get one entity by type and ID.
        
        :param str type_: The entity type to lookup.
        :param int id_: The entity ID to lookup.
        :param bool fetch: Request this entity from the server if not cached?
        
        """
        try:
            return self._cache[(type_, id_)]
        except KeyError:
            return self.find_one(type_, [('id', 'is', id_)])
    
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

            for id_ in missing:
                warnings.warn('%s %d was not found' % (type_, id_), EntityNotFoundWarning)

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
        
    def fetch_heirarchy(self, to_fetch):
        """Populate the parents as far up as we can go, and return all involved.
        
        See :attr:`parent_fields`.
        
        """
        
        all_nodes = set()
        to_resolve = set()
        while to_fetch or to_resolve:

            # Go as far up as we already have for the specified entities.
            for entity in to_fetch:
                all_nodes.add(entity)
                while entity.parent(fetch=False):
                    entity = entity.parent()
                    all_nodes.add(entity)
                if entity['type'] != 'Project':
                    to_resolve.add(entity)
            
            # Bail.
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
            self.find(type_, [['id', 'in'] + ids], [parent_name])
        
        return list(all_nodes)
    
    _guessed_user_lock = threading.Lock()
    
    def guess_user(self, filter=('email', 'starts_with', '{login}@'), fields=(), fetch=True):
        """Guess Shotgun user from current login name.
        
        Looks for $SHOTGUN_USER_ID in your environment, then a user with an
        email that has the login name as the account.
    
        :returns: ``dict`` of ``HumanUser``, or ``None``.
    
        """
        with self._guessed_user_lock:
            
            if not hasattr(self, '_guessed_user'):
                
                # Pull it out of the environment.
                id_ = os.environ.get('SHOTGUN_USER_ID')
                if id_:
                    user = self.merge({'type': 'HumanUser', 'id': int(id_)})
                    Session._guessed_user = user.as_dict()
            
            if not hasattr(self, '_guessed_user'):
                
                if not fetch:
                    return
                
                login = os.getlogin()
                filter_ = tuple(x.format(login=login) for x in filter)
                user = self.find_one('HumanUser', [filter_], fields)
                if user is not None:
                    Session._guessed_user = user.as_dict()
            
            user = getattr(self, '_guessed_user', None)
            if user is None:
                return
            
            entity = self.merge(user)
            if fields:
                entity.fetch(fields) # Not forced!
            
            return entity
        

    

