Overview
========


Getting Started
---------------

All you must do to start using ``sgsession`` is to construct a :class:`~sgsession.session.Session` with an existing `Shotgun <https://github.com/shotgunsoftware/python-api>`_ instance::

    >>> from shotgun_api3 import Shotgun
    >>> from sgsession import Session
    >>> session = Session(Shotgun(*shotgun_args))

From then on you can use the ``session`` as you would have used the Shotgun instance itself.


The Entity
----------

The primary representation of Shotgun entities is the :class:`~sgsession.entity.Entity` class, which extends the familiar dictionary with more Shotgun specific methods and a link back to the session for fetching more fields, parents, etc..


Instance Sharing
----------------

The same :class:`~sgsession.entity.Entity` instance will always be returned for the same conceptual instance. E.g.::

    >>> a = session.find_one('Task', [('code', 'is', 'AA_001')])
    >>> b = session.find_one('Task', [('code', 'is', 'AA_001')])
    >>> a is b
    True


Caching, Merging, and Backrefs
------------------------------

Entities will be cached for the lifetime of their :class:`~sgsession.session.Session`, and any new information about them will be merged in as it is encountered.

For example, fields fetched in subsequent queries to the server will be availible on earlier found entities::

    >>> a = session.find_one('Task', [('code', 'is', 'AA_001')])
    >>> 'sg_status_list' in a
    False
    >>> b = session.find_one('Task', [('code', 'is', 'AA_001')], ['sg_status_list'])
    >>> a['sg_status_list']
    'fin'

Deep-linked fields will also be merged into the main scope of the linked entities for easy referral::

    >>> x = session.find_one('Task', [], ['entity.Shot.code'])
    >>> x['entity']['code']
    'AA_001'

Links to other entities will automatically populate backrefs on the remote side of the link, allowing for entities to easily find there they have been linked from::

    >>> task = session.find_one('Task', [], ['entity'])
    >>> shot = task['entity']
    >>> task in shot.backrefs[('Task', 'entity')]
    True


Important Fields
----------------

Several fields will always be queried for whenever you operate on entities. These include ``Shot.code``, ``Task.step``, and ``project`` on many types. When availible, deep-linked fields will also be fetched, including ``Task.entity.Shot.code``, so even single simple queries will return lots of related data::

    >>> x = session.find_one('Task', [])
    >>> x.pprint()
    Task:456 at 0x101577a20; {
    	entity = Shot:234 at 0x101541a80; {
    		code = 'AA_001'
    		name = 'AA_001'
    		project = Project:123 at 0x101561f30; {
    			name = 'Demo Project'
    		}
    	}
    	project = Project:123 at 0x101561f30; ...
    	sg_status_list = 'fin'
    	step = Step:345 at 0x10155b5e0; {
    		code = 'Matchmove'
    		entity_type = 'Shot'
    		name = 'Matchmove'
    		short_name = 'Matchmove'
    	}
    }


Brace Expansion
---------------

During a ``find`` or ``find_one``, return fields can be specified with brace
expansions to allow for a more compact representation of complex links::

    >>> session.find('Task', [], ['entity.{Asset,Shot}.{name,code}'])


Efficient Heirarchies
---------------------

Ever have a list of tasks that you need to know the full heirarchy for all the way up to the project? With any number of tasks, you can get all of the important fields for the full heirarchy in no more than 3 requests::

    >>> tasks = session.find('Task', some_filters)
    >>> all_entities = session.fetch_heirarchy(tasks)

``all_entities`` is a list of every entity above those tasks, and every entity has been linked and backreffed to each other.
