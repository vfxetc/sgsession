``sgsession.Session``
=====================

.. automodule:: sgsession.session
    
    .. autoclass:: Session


Entity Control
^^^^^^^^^^^^^^
        
.. automethod:: sgsession.session.Session.merge
.. automethod:: sgsession.session.Session.get
.. automethod:: sgsession.session.Session.filter_exists


Fetching Fields
^^^^^^^^^^^^^^^

.. automethod:: sgsession.session.Session.fetch
.. automethod:: sgsession.session.Session.fetch_core
.. automethod:: sgsession.session.Session.fetch_backrefs
.. automethod:: sgsession.session.Session.fetch_heirarchy


Importance Controls
^^^^^^^^^^^^^^^^^^^

These class attributes control which fields are considered "important", which
types are potentially linked to by various fields, and which types are
considered the parent of other types.

.. autoattribute:: sgsession.session.Session.important_fields_for_all
.. autoattribute:: sgsession.session.Session.important_fields
.. autoattribute:: sgsession.session.Session.important_links

.. autoattribute:: sgsession.session.Session.parent_fields


Wrapped Methods
^^^^^^^^^^^^^^^
        
.. automethod:: sgsession.session.Session.create
.. automethod:: sgsession.session.Session.find
.. automethod:: sgsession.session.Session.find_one
.. automethod:: sgsession.session.Session.update
.. automethod:: sgsession.session.Session.delete
.. automethod:: sgsession.session.Session.batch
        
