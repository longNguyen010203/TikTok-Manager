"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.routers.accounts import router as accounts_router
from app.routers.devices import router as devices_router, screen_process_manager
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.redroid_provisionings import router as redroid_provisionings_router
from app.routers.runtimes import router as runtimes_router
from app.services.host_lifecycle import (
    ApplicationLifecycle,
    HostLifecycleManager,
    stop_managed_devices_on_shutdown_from_environment,
)
from app.services.redroid_runtime import RedroidRuntimeAdapter


def create_app(
    host_lifecycle: ApplicationLifecycle | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    lifecycle = host_lifecycle
    if lifecycle is None:
        lifecycle = HostLifecycleManager(
            SessionLocal,
            RedroidRuntimeAdapter(),
            screen_process_manager,
            stop_managed_devices_on_shutdown=(
                stop_managed_devices_on_shutdown_from_environment()
            ),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        lifecycle.startup()
        try:
            yield
        finally:
            lifecycle.shutdown()

    application = FastAPI(title="TikTok Manager API", lifespan=lifespan)
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
    application.include_router(redroid_provisionings_router)
    return application


app = create_app()
