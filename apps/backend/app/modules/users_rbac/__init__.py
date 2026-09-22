"""User & RBAC administration module (users, roles, sessions).

Importing this package registers the module's error codes and exposes the
router used by ``app.main``.  Same 8-file layout as every other module
(schemas, policies, service, repository, events, errors, router).
"""

from app.modules.users_rbac.router import router

__all__ = ["router"]
