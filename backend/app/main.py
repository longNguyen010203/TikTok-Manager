"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.accounts import router as accounts_router
from app.routers.devices import router as devices_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.runtimes import router as runtimes_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="TikTok Manager API")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(accounts_router)
    application.include_router(devices_router)
    application.include_router(jobs_router)
    application.include_router(runtimes_router)
    return application


app = create_app()
