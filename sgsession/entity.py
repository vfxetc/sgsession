import itertools
import sys


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
    
    def pprint(self, backrefs=None, depth=0, visited=None):
        print '%s:%s at 0x%x;' % (self.get('type'), self.get('id'), id(self)),
        
        # Did you know that bools are ints?
        if isinstance(backrefs, bool):
            backrefs = sys.maxint if backrefs else 0
        elif backrefs is not None and not isinstance(backrefs, int):
            backrefs = 0
        
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
                v.pprint(backrefs, depth, visited)
            else:
                print '%s%s = %r' % ('\t' * depth, k, v)
        
        if backrefs is not None:
            for (type_, field), entities in sorted(self.backrefs.iteritems()):
                # Using their wierd filter syntax here.
                print '%s$FROM$%s.%s:' % (
                    '\t' * depth,
                    type_,
                    field,
                ),
                if backrefs > 0:
                    print '['
                    depth += 1
                    for x in entities:
                        print '%s-' % ('\t' * depth, ),
                        x.pprint(backrefs - 1, depth, visited)
                    depth -= 1
                    print '\t' * depth + ']'
                else:
                    print ', '.join(str(x) for x in sorted(x['id'] for x in entities))
        
        depth -= 1
        print '\t' * depth + '}'
    
    
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, self.session.merge(value))
    
    def setdefault(self, key, value):
        return dict.setdefault(self, key, self.session.merge(value))
    
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
    
