import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, auth, drivers, misc, payments, trips

s = get_settings()
logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

if s.sentry_dsn:  # ixtiyoriy monitoring: SENTRY_DSN berilsa va sentry-sdk o'rnatilgan bo'lsa
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=s.sentry_dsn, environment=s.app_env)
    except ImportError:
        log.warning("SENTRY_DSN berilgan, lekin sentry-sdk o'rnatilmagan")

app = FastAPI(title="Viloyatga Boramiz API", version="0.1.0", docs_url="/docs" if s.app_env != "production" else None)
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    t0 = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        log.exception("xato rid=%s %s %s", rid, request.method, request.url.path)
        raise
    log.info("rid=%s %s %s -> %s %.0fms", rid, request.method, request.url.path, resp.status_code, (time.perf_counter() - t0) * 1000)
    resp.headers["x-request-id"] = rid
    return resp


for r in (misc.router, auth.router, drivers.router, trips.router, payments.router, admin.router):
    app.include_router(r, prefix="/api")
