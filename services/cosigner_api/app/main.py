"""FuzeBox Cosigner API entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from . import __version__
from .db import reset_engine
from .routes import pel as pel_routes
from .routes import webhooks as webhooks_routes


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    yield
    await reset_engine()


def create_app() -> FastAPI:
    """Build the FastAPI app. Useful from tests and entrypoints alike."""

    app = FastAPI(
        title="FuzeBox Cosigner API",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(pel_routes.router)
    app.include_router(webhooks_routes.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
