"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers.accounts import router as accounts_router
from app.routers.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="TikTok Manager API")
    application.include_router(health_router)
    application.include_router(accounts_router)
    return application


app = create_app()
