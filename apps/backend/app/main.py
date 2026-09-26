"""TalkFlow Control Plane - FastAPI application entrypoint (reloaded).

Wires the API v1 prefix, the auth / users_rbac / recordings / campaigns
routers, the unified error envelope, tracing/cors middleware and structlog.  Auth-protected routes reject
unauthenticated traffic with `auth.not_authenticated` (401); domain failures
serialize as the single `{error: {...}}` contract.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.tls import TLSEnforcementMiddleware, validate_transport_security
from app.core.tracing import TraceContextMiddleware
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import account_router
from app.modules.auth.router import router as auth_router
from app.modules.calls.router import router as calls_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.compliance.router import router as compliance_router
from app.modules.exports.router import router as exports_router
from app.modules.leads.router import router as leads_router
from app.modules.ops.router import router as ops_router
from app.modules.qa.router import router as qa_router
from app.modules.realtime.router import router as realtime_router
from app.modules.recordings.router import router as recordings_router
from app.modules.rule_sets.router import router as rule_sets_router
from app.modules.scripts.router import router as scripts_router
from app.modules.suppression.router import router as suppression_router
from app.modules.telephony.vicidial_webhooks import router as telephony_router
from app.modules.transfers.router import router as transfers_router
from app.modules.users_rbac.router import router as users_rbac_router
from app.modules.users_rbac.service import seed_roles, seed_super_admin
from app.modules.verifier.router import router as verifier_router
from app.packages.contracts.errors import TalkFlowError, register_core_errors
from app.packages.contracts.version import CONTRACT_VERSION

configure_logging()
register_core_errors()

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fail fast on a plaintext transport, then seed roles + super-admin."""
    validate_transport_security()
    try:
        async with async_session_factory() as db:
            await seed_roles(db)
            await seed_super_admin(db)
    except Exception:
        log.exception("startup seeding failed")
    yield


app = FastAPI(title=settings.app_name, version=CONTRACT_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceContextMiddleware)
app.add_middleware(TLSEnforcementMiddleware)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(account_router, prefix=settings.api_v1_prefix)
app.include_router(users_rbac_router, prefix=settings.api_v1_prefix)
app.include_router(recordings_router, prefix=settings.api_v1_prefix)
app.include_router(campaigns_router, prefix=settings.api_v1_prefix)
app.include_router(scripts_router, prefix=settings.api_v1_prefix)
app.include_router(rule_sets_router, prefix=settings.api_v1_prefix)
app.include_router(compliance_router, prefix=settings.api_v1_prefix)
app.include_router(calls_router, prefix=settings.api_v1_prefix)
app.include_router(leads_router, prefix=settings.api_v1_prefix)
app.include_router(suppression_router, prefix=settings.api_v1_prefix)
app.include_router(exports_router, prefix=settings.api_v1_prefix)
app.include_router(realtime_router, prefix=settings.api_v1_prefix)
app.include_router(telephony_router, prefix=settings.api_v1_prefix)
app.include_router(transfers_router, prefix=settings.api_v1_prefix)
app.include_router(verifier_router, prefix=settings.api_v1_prefix)
app.include_router(analytics_router, prefix=settings.api_v1_prefix)
app.include_router(qa_router, prefix=settings.api_v1_prefix)
app.include_router(ops_router, prefix=settings.api_v1_prefix)


@app.exception_handler(TalkFlowError)
async def talkflow_error_handler(request: Request, exc: TalkFlowError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "") or uuid.uuid4().hex
    log.warning(
        "domain error",
        code=exc.code,
        # Several branches share a code (e.g. every ``require_auth`` rejection is
        # ``auth.not_authenticated``); the message is what distinguishes them.
        message=exc.message,
        status=exc.http_status,
        path=request.url.path,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_envelope(trace_id),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "") or uuid.uuid4().hex
    log.exception("unhandled error", path=request.url.path, trace_id=trace_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal.server_error",
                "message": "An internal error occurred.",
                "status": 500,
                "details": None,
                "traceId": trace_id,
            }
        },
    )


@app.get(settings.api_v1_prefix + "/health")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "traceId": getattr(request.state, "trace_id", ""),
    }
