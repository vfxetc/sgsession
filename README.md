# sgsession

[![Test Status](https://secure.travis-ci.org/westernx/sgsession.png)](http://travis-ci.org/westernx/sgsession)

This Python package is a wrapper around the [Shotgun Python API](https://github.com/shotgunsoftware/python-api) which provides a local data cache and some additional intelligence on top of bare entities.

This is **not** a drop-in replacement for the normal API. While any individual entity in isolation should behave in the same way as with the normal API, the entities are linked behind the scenes and so complex behaviour is likely to break.

Some of the behaviours added include:

- instance sharing for the same entity: the same conceptual entity will be returned as the same instance, instead of seperate but equivalent instances;
- agressive caching and merging: newly found entities will have all the fields that we previously knew them to have;
- `entity.fetch(fields)` to fetch fields if they do not already exist;
- `entity.parent()` to get (and autoload) the logical parent;
- `entity.project()` to get (and autoload) the project;
- `session.fetch_heirarchy(entities)` to get the entire entity graph up to the top `Project`;
- any many more!

Stay tuned for documentation!
