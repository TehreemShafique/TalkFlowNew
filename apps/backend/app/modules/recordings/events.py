"""Recording domain events (written to the outbox, Rule R8).

These map 1:1 to `outbox_table.event_type`; the dispatcher worker translates
them to Kafka topics with the same names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class RecordingEventType:
    """Canonical event names for the recordings domain."""

    PURGED = "recording.purged"
    READY = "recording.ready"
    FAILED = "recording.failed"
    DOWNLOAD_REQUESTED = "recording.download_requested"


@dataclass(slots=True)
class RecordingEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    channel: str = "recordings.events"
    aggregate_type: str = "recording"

    def as_dict(self) -> dict[str, Any]:
        return {
            "eventType": self.event_type,
            "aggregateId": self.aggregate_id,
            "payload": self.payload,
        }
