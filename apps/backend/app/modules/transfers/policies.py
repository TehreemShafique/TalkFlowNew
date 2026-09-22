"""Pure policy functions for transfer lifecycle state transitions (Step 34)."""

from __future__ import annotations

from app.packages.contracts.enums import TransferStatus

_ALLOWED_TRANSITIONS = {
    (TransferStatus.NOT_APPLICABLE.value, TransferStatus.INITIATED.value),
    (TransferStatus.INITIATED.value, TransferStatus.RINGING_VERIFIER.value),
    (TransferStatus.INITIATED.value, TransferStatus.FAILED_NO_VERIFIER.value),
    (TransferStatus.RINGING_VERIFIER.value, TransferStatus.BRIDGED.value),
    (TransferStatus.RINGING_VERIFIER.value, TransferStatus.FAILED_TIMEOUT.value),
    (TransferStatus.RINGING_VERIFIER.value, TransferStatus.FAILED_REJECTED.value),
    (TransferStatus.RINGING_VERIFIER.value, TransferStatus.FAILED_TECHNICAL.value),
    (TransferStatus.BRIDGED.value, TransferStatus.COMPLETED.value),
    (TransferStatus.FAILED_TIMEOUT.value, TransferStatus.RETRY_SCHEDULED.value),
    (TransferStatus.FAILED_NO_VERIFIER.value, TransferStatus.RETRY_SCHEDULED.value),
    (TransferStatus.FAILED_REJECTED.value, TransferStatus.RETRY_SCHEDULED.value),
    (TransferStatus.FAILED_TIMEOUT.value, TransferStatus.CALLBACK_CREATED.value),
    (TransferStatus.FAILED_NO_VERIFIER.value, TransferStatus.CALLBACK_CREATED.value),
    (TransferStatus.FAILED_REJECTED.value, TransferStatus.CALLBACK_CREATED.value),
}


def can_transition_transfer(frm: str, to: str) -> bool:
    if frm == to:
        return True
    return (frm, to) in _ALLOWED_TRANSITIONS
