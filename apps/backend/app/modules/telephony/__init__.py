"""Telephony edge module (BACKEND-8a).

Bridges TalkFlow and the VICIdial/Asterisk dialer: authenticated webhook
ingest (``/telephony/vicidial/start-call`` and ``/dispo-call``), status
disposition mapping, and idempotency replay protection.
"""

from app.modules.telephony.vicidial_webhooks import router

__all__ = ["router"]
