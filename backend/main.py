from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Health check endpoint — used by Railway and monitoring tools."""
    return {"status": "ok"}