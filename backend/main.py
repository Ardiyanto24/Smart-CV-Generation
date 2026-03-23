from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from config import get_settings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from db.limiter import limiter
from routers.auth import router as auth_router
from routers.profile import router as profile_router
from routers.applications import router as applications_router  # baru
from routers.workflow import router as workflow_router          # baru
from routers.output import router as output_router              # baru


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    settings = get_settings()

    if settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment="production",
            traces_sample_rate=1.0,
        )
    # TODO Phase 4: Verify DB connection
    yield
    # ── Shutdown ─────────────────────────────────────────
    # TODO Phase 4: Clean up resources if needed


app = FastAPI(
    title="CV Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"},
    )

# ── Routers ───────────────────────────────────────────────────────────────────
# Urutan penting — applications harus sebelum workflow dan output
# karena ketiganya share prefix /applications
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(profile_router)
app.include_router(applications_router)  # baru
app.include_router(workflow_router)      # baru
app.include_router(output_router)        # baru

# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint — used by Railway and monitoring tools."""
    return {"status": "ok"}