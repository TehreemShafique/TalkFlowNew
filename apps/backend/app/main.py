"""TalkFlow Control Plane - FastAPI application entrypoint.

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
from app.core.tracing import TraceContextMiddleware
from app.modules.auth import router as auth_router
from app.modules.calls import router as calls_router
from app.modules.campaigns import router as campaigns_router
from app.modules.exports import router as exports_router
from app.modules.leads import router as leads_router
from app.modules.recordings import router as recordings_router
from app.modules.scripts import router as scripts_router
from app.modules.suppression import router as suppression_router
from app.modules.users_rbac import router as users_rbac_router
from app.modules.users_rbac.service import seed_roles, seed_super_admin
from app.packages.contracts.errors import TalkFlowError, register_core_errors

configure_logging()
register_core_errors()

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed roles + the super-admin account on boot (idempotent)."""
    try:
        async with async_session_factory() as db:
            await seed_roles(db)
            await seed_super_admin(db)
    except Exception:
        log.exception("startup seeding failed")
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceContextMiddleware)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(users_rbac_router, prefix=settings.api_v1_prefix)
app.include_router(recordings_router, prefix=settings.api_v1_prefix)
app.include_router(campaigns_router, prefix=settings.api_v1_prefix)
app.include_router(scripts_router, prefix=settings.api_v1_prefix)
app.include_router(calls_router, prefix=settings.api_v1_prefix)
app.include_router(leads_router, prefix=settings.api_v1_prefix)
app.include_router(suppression_router, prefix=settings.api_v1_prefix)
app.include_router(exports_router, prefix=settings.api_v1_prefix)


@app.exception_handler(TalkFlowError)
async def talkflow_error_handler(request: Request, exc: TalkFlowError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "") or uuid.uuid4().hex
    log.warning("domain error", code=exc.code, status=exc.http_status, path=request.url.path)
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
    return {"status": "ok", "service": settings.app_name, "traceId": getattr(request.state, "trace_id", "")}