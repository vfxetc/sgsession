import itertools


class Session(object):
    
    _parent_fields = {
        'Asset': 'project',
        'Project': None,
        'Sequence': 'project',
        'Shot': 'sg_sequence',
        'Task': 'entity',
    }
    
    _important_fields_for_all = ['project']
    _important_fields = {
        'Asset': ['code', 'sg_asset_type'],
        'Project': ['code', 'sg_code'],
        'Sequence': ['code'],
        'Shot': ['code', 'sg_sequence'],
        'Task': ['step', 'entity'],
    }
    
    def __init__(self, shotgun=None):
        self.shotgun = shotgun
        self.cache = {}
    
    def __getattr__(self, name):
        return getattr(self.shotgun, name)
    
    def merge(self, *args, **kwargs):
        
        # Get our one argument.
        if len(args) > 1 or args and kwargs:
            raise ValueError('must provide one arg or kwargs, not both')
        data = args[0] if args else kwargs
                
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
            entity.update(data)
            return entity
        
        # Return the new one.
        self.cache[key] = new
        new.update(data)
        return new
    
    def create(self, type_, data):
        return self.merge(self.shotgun.create(type_, data))

    def update(self, type_, id, data):
        return self.merge(self.shotgun.update(type_, id, data))

    def batch(self, requests):
        return [self.merge(x) if isinstance(x, dict) else x for x in self.shotgun.batch(requests)]
    
    def find(self, type_, filters, fields=None, *args, **kwargs):
        
        fields = list(fields) if fields else ['id']
        fields.extend(self._important_fields_for_all)
        fields.extend(self._important_fields.get(type_, []))
        
        return [self.merge(x) for x in self.shotgun.find(type_, filters, fields, *args, **kwargs)]
    
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
        
        if isinstance(fields, basestring):
            fields = [fields]
            
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

    def fetch_core(self, to_fetch):
        by_type = {}
        for x in to_fetch:
            by_type.setdefault(x['type'], set()).add(x)
        for type_, entities in by_type.iteritems():
            self._fetch(entities,
                self._important_fields_for_all +
                self._important_fields.get(type_, [])
            )
        
    def fetch_heirarchy(self, to_fetch):
        """Populate the parents as far up as we can go."""
        
        to_resolve = set()
        while to_fetch or to_resolve:

            # Go as far up as we already have for the specified entities.
            for entity in to_fetch:
                while entity.parent(fetch=False):
                    entity = entity.parent()
                if entity['type'] != 'Project':
                    to_resolve.add(entity)
            
            # Bail.
            if not to_resolve:
                break
            
            # Find the type that we have the most entities of, and remove them
            # from the list to resolve.
            by_type = {}
            for x in to_resolve:
                by_type.setdefault(x['type'], set()).add(x)
            type_, to_fetch = max(by_type.iteritems(), key=lambda x: len(x[1]))
            to_resolve.difference_update(to_fetch)
            
            # Fetch the parent names.
            ids = [x['id'] for x in to_fetch]
            parent_name = self._parent_fields[type_]
            self.find(type_, [['id', 'in'] + ids], [parent_name])
    

    



class Entity(dict):
    
    @staticmethod
    def _cache_key(data):
        type_ = data.get('type')
        id_ = data.get('id')
        if type_ and id_:
            return (type_, id_)
        elif type_:
            return ('New-%s' % type_, id(data))
        else:
            return ('Unknown', id_)
    
    def __init__(self, type_, id_, session):
        dict.__init__(self, type=type_, id=id_)
        self.session = session
        self.backrefs = {}
    
    @property
    def cache_key(self):
        return self._cache_key(self)
    
    def __repr__(self):
        return '<Entity %s:%s at 0x%x>' % (self.get('type'), self.get('id'), id(self))
    
    def __hash__(self):
        type_ = self.get('type')
        id_ = self.get('id')
        if not (type_ and id_):
            raise TypeError('entity must have type and id to be hashable')
        return hash((type_, id_))
    
    def pprint(self, depth=0, visited=None):
        print '%s:%s at 0x%x;' % (self.get('type'), self.get('id'), id(self)),
        
        visited = visited or set()
        if id(self) in visited:
            print '...'
            return
        visited.add(id(self))
        
        if len(self) <= 2:
            print '{}'
            return
        
        print '{' 
        depth += 1
        for k, v in sorted(self.iteritems()):
            if k in ('id', 'type'):
                continue
            if isinstance(v, Entity):
                print '%s%s =' % ('\t' * depth, k),
                v.pprint(depth, visited)
            else:
                print '%s%s = %r' % ('\t' * depth, k, v)
        depth -= 1
        print '\t' * depth + '}'
    
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, self.session.merge(value))
    
    def setdefault(self, key, value):
        dict.setdefault(self, key, self.session.merge(value))
    
    def update(self, *args, **kwargs):
        for x in itertools.chain(args, [kwargs]):
            self._update(self, x, 0)
    
    def _update(self, dst, src, depth):
        # print ">>> MERGE", depth, dst, '<-', src
        for k, v in src.iteritems():
            
            if isinstance(v, dict):
                v = self.session.merge(v)
                # If the destination is not an entity, or the type or ID does
                # not match (and so is a different entity) then replace it.
                if (not isinstance(dst.get(k), Entity) or
                    dst[k] is v or
                    dst[k]['type'] != v['type'] or
                    dst[k]['id']   != v['id']
                ):
                    # Establish backref.
                    v.backrefs.setdefault((dst['type'], k), []).append(dst)
                    # Set the attribute.
                    dst[k] = v
                else:
                    self._update(dst[k], v, depth + 1)
            else:
                dst[k] = v
        # print "<<< MERGE", depth, dst
        
    
    def copy(self):
        raise RuntimeError("cannot copy %s" % self.__class__.__name__)
    
    def fetch(self, *args, **kwargs):
        self.session.fetch([self], *args, **kwargs)
    
    def fetch_core(self):
        self.session.fetch_core([self])
    
    def fetch_heirarchy(self):
        self.session.fetch_heirarchy([self])
    
    def parent(self, fetch=True):
        
        try:
            field = self.session._parent_fields[self['type']]
        except KeyError:
            raise KeyError('%s does not have a parent type defined' % self['type'])
        
        # Fetch it if it exists (e.g. this isn't a Project) and we are allowed
        # to fetch.
        if field and fetch:
            self.fetch(field)
            self.setdefault(field, None)
        
        return self.get(field)
    
    def project(self, fetch=True):
        
        # The most straightforward way.
        try:
            return self['project']
        except KeyError:
            pass
        
        # Pass up the parental chain looking for a project.
        project = None
        parent = self.parent(fetch=False)
        if parent:
            if parent['type'] == 'Project':
                project = parent
            else:
                project = parent.project()
        
        # If we were given one from the parent, assume it.
        if project:
            self['project'] = project
            return project
        
        if fetch:
            # Fetch it ourselves; this should happen to the uppermost in a
            # heirachy that is not a Project.
            self.fetch(['project'])
            return self.setdefault('project', None)
        
    
    def fetch_to_project(self):
        pass
        
        cache = {}
        entities = copy.deepcopy(list(entities))
        to_resolve = entities[:]
        
        while to_resolve:
            entity = to_resolve.pop(0)
            
            cache_key = (entity['type'], entity['id'])
            cache[cache_key] = entity
            
            # Figure out where to find parents.
            parent_attr = utils.parent_fields.get(entity['type'])
            
            # Doesn't have a parent.
            if not parent_attr:
                continue

            # It is already there.
            if parent_attr in entity:
                parent = entity[parent_attr]
            
            # Get the parent.
            else:
                parent = self.shotgun.find(entity['type'], [
                    ('id', 'is', entity['id']),
                ], (parent_attr, ))[0][parent_attr]
            
            parent_key = (parent['type'], parent['id'])
            parent = cache.setdefault(parent_key, parent)
            
            # Mark it down, and prepare for next loop.
            entity[parent_attr] = parent
            to_resolve.append(parent)
        
        return entities
    
