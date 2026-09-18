"""Distributed tracing primitives - trace-id propagation on the wire.

Every response carries `X-Trace-Id`; errors bake the same id into their
envelope (see main.py error handler).  No vendor SDK required.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def trace_id() -> str:
    return _trace_id_var.get()


class TraceContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        rid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        token = _trace_id_var.set(rid)
        request.state.trace_id = rid
        try:
            response = await call_next(request)
        finally:
            _trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = rid
        return response