"""Request-scoped identity and access context (Rule R5).

Always built from the authenticated principal - never derived from the request
body.  `AccessScope` hands a stored procedure an explicit set of constraints;
a NO-defaults rule keeps callers honest at the dependency layer instead of
silently widening scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AccessScope:
    """Constraints applied to a data access call.

    `flow` is "granted" when the access was authorized by an explicit JWT
    capability, "session" when it flowed from the primary authentication token.
    """

    user_id: UUID | None = None
    tenant_id: str | None = None
    role: str | None = None
    permissions: set[str] = field(default_factory=set)
    scope_layer: str = "tier1"
    origin: str = "internal"
    flow: str = "session"

    @classmethod
    def anonymous(cls) -> AccessScope:
        """A scope with no tenant/user - denied by default (Rule R6)."""
        return cls()

    @classmethod
    def from_grant(cls, token: dict) -> AccessScope:
        """Scope derived from a signed capability grant (playback/download)."""
        return cls(
            user_id=token.get("sub"),
            flow="granted",
            origin="grant",
            permissions={"recording.view"},
        )

    def has(self, permission: str) -> bool:
        return self.permissions is not None and permission in self.permissions


@dataclass(frozen=True, slots=True)
class UserContext:
    """Authenticated principal resolved from the access token."""

    user_id: UUID
    tenant_id: str | None
    role: str
    permissions: set[str]
    issued_at: datetime | None = None
    scope: AccessScope = field(default_factory=AccessScope)
    # Session JWT id (``user_sessions.token_id``).  Carried so a handler that
    # must re-issue the token can reuse the same jti and keep resolving to the
    # same ledger row instead of orphaning it.
    session_token_id: str | None = None

    @classmethod
    def from_principal(
        cls,
        *,
        user_id: UUID,
        role: str,
        permissions: set[str],
        tenant_id: str | None = None,
        issued_at: datetime | None = None,
        session_token_id: str | None = None,
    ) -> UserContext:
        """Scope + context derived from a freshly resolved DB principal."""
        now = datetime.now(UTC)
        scope = AccessScope(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role or None,
            permissions=permissions,
            flow="session",
        )
        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role or "agent",
            permissions=permissions,
            issued_at=issued_at or now,
            scope=scope,
            session_token_id=session_token_id,
        )
