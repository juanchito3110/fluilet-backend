"""No request bodies, exception text, SQL values or document contents are logged."""

import asyncio
import time
from collections import OrderedDict, deque

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings


async def validation_error(request: Request, exc: RequestValidationError):
    # Pydantic's default errors contain the rejected input and exception context.
    return JSONResponse(
        {
            "detail": "Solicitud inválida.",
            "errors": [
                {
                    "type": e["type"],
                    "loc": [
                        part
                        if isinstance(part, int)
                        or str(part)
                        in {
                            "body",
                            "query",
                            "path",
                            "header",
                            "text",
                            "password",
                            "email",
                            "role",
                            "name",
                            "full_name",
                            "nivel_simplificacion_nlp",
                            "category",
                            "topic",
                            "custom_topic",
                            "target_level",
                            "age_group",
                            "simplification_level",
                            "child_id",
                            "comprehension_score",
                            "questions_answered",
                            "questions_correct",
                            "tts_speed_used",
                            "birth_date",
                            "pin",
                        }
                        else "field"
                        for part in e["loc"]
                    ],
                }
                for e in exc.errors()
            ],
        },
        status_code=422,
    )


class PrivacyMiddleware:
    """Bounded in-memory body reception before FastAPI's form/JSON parsing.

    Multipart is intentionally unsupported: file endpoints accept raw bytes.
    X-Forwarded-For is not trusted here. Configure the proxy and uvicorn trust list.
    """

    def __init__(self, app):
        self.app = app
        self.buckets = OrderedDict()

    def limited(self, scope):
        client = scope.get("client") or ("unknown", 0)
        path = scope.get("path", "")
        sensitive = path.startswith("/api/v1/auth/") or path.endswith("/session")
        key = (client[0], sensitive)
        now = time.monotonic()
        # Expire inactive buckets without retaining documents, names or usernames.
        while self.buckets and next(iter(self.buckets.values()))[-1] <= now - 60:
            self.buckets.popitem(last=False)
        bucket = self.buckets.get(key)
        if bucket is None:
            if len(self.buckets) >= 10000:
                return True
            bucket = self.buckets[key] = deque()
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        limit = settings.AUTH_REQUESTS_PER_MINUTE if sensitive else settings.REQUESTS_PER_MINUTE
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        self.buckets.move_to_end(key)
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        async def reject(code, message):
            response = JSONResponse(
                {"detail": message},
                status_code=code,
                headers={"Retry-After": "60"} if code == 429 else None,
            )
            await response(scope, receive, safe_send)

        if scope.get("path") not in {"/health/live", "/health/ready"} and self.limited(scope):
            return await reject(429, "Límite de solicitudes alcanzado.")
        headers = dict(scope.get("headers", []))
        if headers.get(b"content-type", b"").lower().startswith(b"multipart/"):
            return await reject(415, "Envía el archivo como cuerpo binario PDF/TXT, sin multipart.")
        if headers.get(b"content-encoding", b"identity").lower() != b"identity":
            return await reject(415, "Codificación de transporte no admitida.")
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError()
        except ValueError:
            return await reject(400, "Longitud inválida.")
        if length > settings.MAX_BODY_BYTES:
            return await reject(413, "El tamaño máximo es 5 MB.")
        body = bytearray()
        try:
            async with asyncio.timeout(settings.BODY_TIMEOUT_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    part = message.get("body", b"")
                    if len(body) + len(part) > settings.MAX_BODY_BYTES:
                        return await reject(413, "El tamaño máximo es 5 MB.")
                    body.extend(part)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "Tiempo de recepción agotado.")
        delivered = False

        async def memory_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        try:
            await self.app(scope, memory_receive, safe_send)
        except Exception:
            # Do not propagate exceptions to uvicorn: default traceback formatters
            # can expose SQL parameters or parser/model inputs.
            if not started:
                await reject(500, "No fue posible completar la solicitud.")
        finally:
            body.clear()
