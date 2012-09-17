import itertools
from .entity import Entity


class Session(object):
    
    _parent_fields = {
        'Asset': 'project',
        'Project': None,
        'Sequence': 'project',
        'Shot': 'sg_sequence',
        'Task': 'entity',
    }
    
    _important_fields_for_all = ['updated_at']
    _important_fields = {
        'Asset': ['project', 'code', 'sg_asset_type'],
        'Sequence': ['project', 'code'],
        'Shot': ['project', 'code'],
        'Step': ['code', 'short_name', 'entity_type'],
        'Task': ['step', 'project'],
    }
    
    _important_links = {
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
        }
    }
    
    def __init__(self, shotgun=None):
        self.shotgun = shotgun
        self.cache = {}
    
    def __getattr__(self, name):
        return getattr(self.shotgun, name)
    
    def merge(self, data, over=None):
        
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
        return self.merge(self.shotgun.create(type_, data))

    def update(self, type_, id, data):
        return self.merge(self.shotgun.update(type_, id, data))

    def batch(self, requests):
        return [self.merge(x) if isinstance(x, dict) else x for x in self.shotgun.batch(requests)]
    
    def find(self, type_, filters, fields=None, *args, **kwargs):
        
        fields = list(fields) if fields else ['id']
        
        # Add important fields for this type.
        fields.extend(self._important_fields_for_all)
        fields.extend(self._important_fields.get(type_, []))
        
        # Add parent.
        parent_field = self._parent_fields.get(type_)
        if parent_field:
            fields.append(parent_field)
        
        # Add important deep-fields for requested type.
        for local_field, link_types in self._important_links.get(type_, {}).iteritems():
            fields.append(local_field)
            for link_type in link_types:
                remote_fields = self._important_fields.get(link_type, [])
                for remote_field in itertools.chain(self._important_fields_for_all, remote_fields):
                    fields.append('%s.%s.%s' % (local_field, link_type, remote_field))
        
        result = self.shotgun.find(type_, filters, list(set(fields)), *args, **kwargs)
        return [self.merge(x, over=True) for x in result]
        
    
    def find_one(self, entity_type, filters, fields=None, order=None, 
        filter_operator=None, retired_only=False):
        results = self.find(entity_type, filters, fields, order, 
            filter_operator, 1, retired_only)
        if results:
            return results[0]
        return None
    
    def get(self, type_, id_, fetch=True):
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
    
    def fetch(self, to_fetch, fields, *args, **kwargs):
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self._fetch(entities, fields, *args, **kwargs)

    def fetch_backrefs(self, to_fetch, backref_type, field):
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self.find(backref_type, [[field, 'is'] + [x.minimal for x in entities]])

    def fetch_core(self, to_fetch):
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self._fetch(entities, itertools.chain(
                self._important_fields_for_all,
                self._important_fields.get(type_) or (),
                self._important_links.get(type_, {}).iterkeys(),
            ))
        
    def fetch_heirarchy(self, to_fetch):
        """Populate the parents as far up as we can go, and return all involved."""
        
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
            parent_name = self._parent_fields[type_]
            self.find(type_, [['id', 'in'] + ids], [parent_name])
        
        return list(all_nodes)
    

    

