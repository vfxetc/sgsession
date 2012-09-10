import itertools
import sys
import re


class Entity(dict):
    
    def __init__(self, type_, id_, session):
        dict.__init__(self, type=type_, id=id_)
        self.session = session
        self.backrefs = {}
    
    @property
    def cache_key(self):
        type_ = dict.get(self, 'type')
        id_ = dict.get(self, 'id')
        if type_ and id_:
            return (type_, id_)
        elif type_:
            return ('Detached-%s' % type_, id(self))
        elif id_:
            return ('Unknown', id_)
        else:
            return ('Detached-Unknown', id(self))
    
    @property
    def minimal(self):
        return dict(type=self['type'], id=self['id'])
    
    def as_dict(self, visited=None):
        if visited is None:
            visited = set()
        if self in visited:
            return self.minimal
        visited.add(self)
        ret = {}
        for k, v in self.iteritems():
            if isinstance(v, Entity):
                ret[k] = v.as_dict(visited)
            else:
                ret[k] = v
        return ret
    
    def __repr__(self):
        return '<Entity %s:%s at 0x%x>' % (self.get('type'), self.get('id'), id(self))
    
    def __hash__(self):
        type_ = dict.get(self, 'type')
        id_ = dict.get(self, 'id')
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
        
        # Pre-process deep linked names.
        for k, v in src.items():
            m = re.match(r'^(\w+)\.([A-Z]\w+)\.(.*)$', k)
            if m:
                field, type_, deep_field = m.groups()
                if isinstance(src.setdefault(field, {}), dict):
                    src[field].setdefault('type', type_)
                    src[field][deep_field] = v
                elif v is not None:
                    raise ValueError('Setting deep value on non-dict')
                # XXX: Is this dangerous?
                del src[k]
        
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
    
    def get(self, fields, default=None):
        """Get field value(s) if they exist, otherwise a default.
        
        :param fields: A ``str`` field name or collection of ``str`` field names.
        :param default: Default value to return when field does not exist.
        
        If passed a single field name as a ``str``, return the coresponding value.
        If passed field names as a list or tuple, return a tuple of coresponding values.
        
        """
        if isinstance(fields, (tuple, list)):
            return tuple(dict.get(self, x, default) for x in fields)
        else:
            return dict.get(self, fields, default)
    
    def fetch(self, fields, default=None, force=False):
        """Get field value(s), automatically fetching them from the server.
        
        :param fields: A ``str`` field name or collection of ``str`` field names.
        :param default: Default value to return when field does not exist.
        :param bool force: Force an update from the server, otherwise only query
            they server if fields have been requested that we do not already have.
        
        If passed a single field name as a ``str``, return the coresponding value.
        If passed field names as a list or tuple, return a tuple of coresponding values.
        
        """
        is_single = not isinstance(fields, (tuple, list))
        if is_single:
            fields = [fields]
        self.session.fetch([self], fields, force=force)
        if is_single:
            return dict.get(self, fields[0], default)
        else:
            return tuple(dict.get(self, x, default) for x in fields)

    def fetch_core(self):
        """Assert that all "important" fields exist on this Entity."""
        self.session.fetch_core([self])
    
    def fetch_heirarchy(self):
        """Fetch the full upward heirarchy (toward the Project) from the server."""
        self.session.fetch_heirarchy([self])
    
    def fetch_backrefs(self, type_, field):
        """Fetch all backrefs to this Entity from the given type and field."""
        self.session.fetch_backrefs([self], type_, field)
    
    def parent(self, fetch=True):
        """Get the parent of this Entity, automatically fetching from the server."""
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
        """Get the project of this Entity, automatically fetching from the server.
        
        Depending on what part of the heirarchy is already loaded, many more
        entities will have their Project fetched by this single call.
        
        """
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
    
