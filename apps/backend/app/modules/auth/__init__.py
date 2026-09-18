"""Auth module: login/pin-login, signup, session tracking, /me.

Importing this package registers the module's error codes and exposes the
router used by ``app.main``.  Same 8-file layout as every other module
(schemas, policies, service, repository, events, errors, router).
"""
from app.modules.auth.router import router

__all__ = ["router"]