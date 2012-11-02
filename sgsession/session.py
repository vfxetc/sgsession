"""The Session is a wrapper around a Shotgun instance, proxying requests to
the server and applying additional logic on top of it. The Session instance is
designed to be used for a single task and then discarded, since it makes the
assumption that entity relationships do not change.

While not fully documented below, this object will proxy all attributes to the
underlying Shotgun instance, so you can treat this as you would a Shotgun
instance.

"""

import itertools
import time

from .entity import Entity


class Session(object):
    
    """Constructor; give it a Shotgun instance."""
    
    #: Mapping of entity types to the type of their "parent".
    parent_fields = {
        'Asset': 'project',
        'Project': None,
        'Sequence': 'project',
        'Shot': 'sg_sequence',
        'Task': 'entity',
        'PublishEvent': 'sg_link',
    }
    
    #: Fields to always fetch.
    important_fields_for_all = ['updated_at']
    
    #: Fields to always fetch: maps entity type to a list of fields.
    important_fields = {
        'Asset': ['code', 'sg_asset_type'],
        'Project': ['name'],
        'Sequence': ['code'],
        'Shot': ['code'],
        'Step': ['code', 'short_name', 'entity_type'],
        'Task': ['step', 'content'],
        'PublishEvent': ['code', 'sg_type', 'sg_version'],
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
    
    def __init__(self, shotgun=None):
        self.shotgun = shotgun
        self.cache = {}
    
    def __getattr__(self, name):
        return getattr(self.shotgun, name)
    
    def merge(self, data, over=None):
        """Import a raw entity into the session.
        
        :param dict data: The raw fields to convert into an :class:`~sgsession.entity.Entity`.
        :param bool over: Control for merge behaviour with existing data.
            ``True`` results in the new data taking precedence, and ``False``
            the old data. The default of ``None`` will automatically decide
            based on the ``updated_at`` field.
        
        :return: The :class:`~sgsession.entity.Entity`. This will not be a new instance if the
            entity was already in the session, but it will have all the newly
            merged data in it.
        
        """
        
        if isinstance(data, (list, tuple)):
            return tuple(self.merge(x, over) for x in data)
                
        # Non-dicts (including Entities) don't matter; just pass them through.
        if not isinstance(data, dict):
            return data
            
        # Pass through entities if they are owned by us.
        if isinstance(data, Entity):
            if data.session is not self:
                raise ValueError('entity not owned by this session')
            return data
        
        # If it already exists, then merge this into the old one.
        new = Entity(data.get('type'), data.get('id'), self)
        key = new.cache_key
        if key in self.cache:
            entity = self.cache[key]
            entity._update(entity, data, over=over)
            return entity
        
        # Return the new one.
        self.cache[key] = new
        new._update(new, data, over=over)
        return new
    
    def create(self, type_, data):
        """Create an entity of the given type and data.
        
        :return: The new :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-create>`_
        
        """
        return self.merge(self.shotgun.create(type_, data))

    def update(self, type_, id, data):
        """Update the given entity with the given fields.
        
        .. todo:: Add this to the Entity.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-update>`_
        
        """
        return self.merge(self.shotgun.update(type_, id, data))

    def batch(self, requests):
        """Perform a series of requests in a transaction.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-batch>`_
        
        """
        return [self.merge(x) if isinstance(x, dict) else x for x in self.shotgun.batch(requests)]
    
    def find(self, type_, filters, fields=None, *args, **kwargs):
        """Find entities.
        
        :return: :class:`list` of found :class:`~sgsession.entity.Entity`.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-find>`_
        
        """
        
        fields = list(fields) if fields else ['id']
        
        # Add important fields for this type.
        fields.extend(self.important_fields_for_all)
        fields.extend(self.important_fields.get(type_, []))
        
        # Add parent.
        parent_field = self.parent_fields.get(type_)
        if parent_field:
            fields.append(parent_field)
        
        # Add important deep-fields for requested type.
        for local_field, link_types in self.important_links.get(type_, {}).iteritems():
            fields.append(local_field)
            for link_type in link_types:
                remote_fields = self.important_fields.get(link_type, [])
                remote_links = self.important_links.get(link_type, {})
                for remote_field in itertools.chain(self.important_fields_for_all, remote_fields, remote_links.iterkeys()):
                    fields.append('%s.%s.%s' % (local_field, link_type, remote_field))
        
        fields = sorted(set(fields))
        
        start_time = time.time()
        result = self.shotgun.find(type_, filters, fields, *args, **kwargs)
        print '%.3fms' % ((time.time() - start_time) * 1000)
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
    
    def delete(self, entity_type, entity_id):
        """Delete one entity.
        
        .. warning:: This session will **not** forget about the deleted entity,
            and all links from other entities will remain intact.
        
        `See the Shotgun docs for more. <https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#wiki-delete>`_
        
        """
        return self.shotgun.delete(entity_type, entity_id)
        
    def get(self, type_, id_, fetch=True):
        """Get one entity by type and ID.
        
        :param str type_: The entity type to lookup.
        :param int id_: The entity ID to lookup.
        :param bool fetch: Request this entity from the server if not cached?
        
        """
        try:
            return self.cache[(type_, id_)]
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
            self.find(
                type_,
                [['id', 'in'] + list(ids_)],
                fields,
            )
    
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
    

    

