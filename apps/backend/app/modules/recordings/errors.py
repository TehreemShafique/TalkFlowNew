"""Recordings module error codes (registered into the central registry)."""

from __future__ import annotations

from app.packages.contracts.errors import (
    GoneError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    register_error,
)

# Registration is idempotent; import-time side effect builds the HTTP map.
register_error("recording.not_found", 404, "Recording not found.")
register_error(
    "recording.purged_or_expired", 410, "Recording has been purged or expired."
)
register_error("recording.source_unavailable", 503, "Recording source is unavailable.")
register_error("recording.download_unauthorized", 403, "Not authorized to download.")
register_error(
    "recording.purge_unauthorized", 403, "Not authorized to purge this recording."
)

# Typed exceptions (exported for the service/router).
RecordingNotFoundError = NotFoundError  # code "recording.not_found"
RecordingPurgedError = GoneError  # code "recording.purged_or_expired"
RecordingSourceUnavailableError = (
    ServiceUnavailableError  # code "recording.source_unavailable"
)
RecordingDownloadUnauthorizedError = (
    PermissionDeniedError  # code "recording.download_unauthorized"
)
RecordingPurgeUnauthorizedError = (
    PermissionDeniedError  # code "recording.purge_unauthorized"
)
