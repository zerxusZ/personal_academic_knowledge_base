import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # ── Incoming ─────────────────────────────────────────────────────
        log.info(
            "[%s] --> %s %s | client=%s | UA=%s",
            req_id,
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", "-")[:60],
        )
        if request.query_params:
            log.debug("[%s]     query_params=%s", req_id, dict(request.query_params))

        # Read body for DEBUG (only for non-streaming, small payloads)
        body_bytes = b""
        if request.method in ("POST", "PUT", "PATCH"):
            body_bytes = await request.body()
            if body_bytes:
                body_preview = body_bytes[:500].decode("utf-8", errors="replace")
                log.debug("[%s]     body(preview)=%s", req_id, body_preview)
            # Rebuild so downstream can still read it
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request = Request(request.scope, receive)

        # ── Process ───────────────────────────────────────────────────────
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            log.error(
                "[%s] <-- EXCEPTION %s | %.1fms | %s",
                req_id, request.url.path, elapsed, exc,
                exc_info=True,
            )
            raise

        # ── Outgoing ──────────────────────────────────────────────────────
        elapsed = (time.perf_counter() - start) * 1000
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        log.log(
            level,
            "[%s] <-- %s %s | %d | %.1fms",
            req_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        response.headers["X-Request-Id"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed:.1f}"
        return response
