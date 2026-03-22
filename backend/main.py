from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from db.limiter import limiter
from routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    # TODO Phase 4: Initialize Sentry
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

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint — used by Railway and monitoring tools."""
    return {"status": "ok"}