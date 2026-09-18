"""Export pipeline module (spec section 28.8 exports + reporting).

Request -> queued -> (processing) -> ready is executed synchronously in the
request but fully persisted on the ``exports`` job row; the CSV artifact lives
in object storage and DOWNLOADs are permission-gated + audit-logged.
"""

from app.modules.exports.router import router

__all__ = ["router"]