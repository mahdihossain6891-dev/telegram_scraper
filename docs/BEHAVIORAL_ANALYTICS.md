"""Behavioral Analytics — isolated module documentation.

Enable
------
- Backend: ``behavioral_analytics.py`` + ``/api/behavioral/*`` in ``server.py``
- Frontend: ``/behavioral-analytics`` page + ``/api/behavioral/[...path]`` proxy
- Storage: MongoDB collection ``behavioral_analytics`` only

Disable
-------
1. Remove or stop linking ``/behavioral-analytics`` from the sidebar.
2. Optionally drop the FastAPI routes under ``/api/behavioral``.
3. Optionally drop the Mongo collection: ``db.behavioral_analytics.drop()``.

No other application features read from or write to this collection.
Message scraping, keyword alerting, and existing dashboards are unaffected.

Rebuild
-------
POST ``/api/behavioral/rebuild`` recomputes all profiles from existing
``messages``, ``users``, ``chats``, and optionally overlays content risk from
``user_activity``. Source collections are never modified.
"""
