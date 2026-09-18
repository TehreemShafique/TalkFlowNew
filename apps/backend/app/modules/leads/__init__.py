"""Leads module - master contact registry + resumable CSV import wizard.

The physical ``leads`` table is extended in-place by the module migration
(d6e7f8a9b0c1); ``lead_import_jobs`` makes the import resumable (upload ->
mapping -> validating -> commit) and idempotent (a second commit on a
``completed`` job is a no-op).  Same 8-file layout as every other module.
"""

from app.modules.leads.router import router

__all__ = ["router"]