"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import DATABASE_SETTINGS, SessionLocal, engine
from app.routers.accounts import router as accounts_router
from app.routers.artifacts import router as artifacts_router
from app.routers.content import router as content_router, delivery_router
from app.routers.devices import router as devices_router, screen_process_manager
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.managed_apps import router as managed_apps_router
from app.routers.redroid_provisionings import router as redroid_provisionings_router
from app.routers.runtime_networks import router as runtime_networks_router
from app.routers.runtimes import router as runtimes_router
from app.routers.runtime_apps import router as runtime_apps_router
from app.routers.publishing import router as publishing_router
from app.routers.workflows import router as workflows_router, template_router as workflow_templates_router
from app.services.host_lifecycle import (
    ApplicationLifecycle,
    HostLifecycleManager,
    stop_managed_devices_on_shutdown_from_environment,
)
from app.services.database_startup import DatabaseStartupValidator
from app.services.android_network import AndroidNetworkAdapter
from app.services.network_config import RuntimeNetworkSettings
from app.services.network_credentials import MasterKeyManager, NetworkCredentialProvider
from app.services.network_operation_lock import RuntimeNetworkOperationGuard
from app.services.network_secrets import SecretResolver
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_network_orchestration import RuntimeNetworkRecoveryCoordinator
from app.services.systemd_proxy_bridge import SystemdHostProxyBridgeSupervisor
from app.config import load_application_config


def create_app(
    host_lifecycle: ApplicationLifecycle | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    lifecycle = host_lifecycle
    if lifecycle is None:
        runtime_adapter = RedroidRuntimeAdapter()
        network_settings = RuntimeNetworkSettings.from_environment()
        application_config = load_application_config()
        credential_provider = NetworkCredentialProvider(
            MasterKeyManager(application_config.credential_key_path)
        )
        lifecycle = HostLifecycleManager(
            SessionLocal,
            runtime_adapter,
            screen_process_manager,
            stop_managed_devices_on_shutdown=(
                stop_managed_devices_on_shutdown_from_environment()
            ),
            network_reconciler=RuntimeNetworkRecoveryCoordinator(
                SessionLocal,
                runtime_adapter=runtime_adapter,
                android_adapter=AndroidNetworkAdapter(),
                bridge_supervisor=SystemdHostProxyBridgeSupervisor(
                    network_settings
                ),
                secret_resolver=SecretResolver(),
                guard=RuntimeNetworkOperationGuard(
                    network_settings.lock_directory
                ),
                credential_provider=credential_provider,
            ),
            database_readiness_check=DatabaseStartupValidator(
                engine, DATABASE_SETTINGS, credential_provider
            ).validate,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        lifecycle.startup()
        try:
            yield
        finally:
            lifecycle.shutdown()

    application = FastAPI(title="TikTok Manager API", lifespan=lifespan)

    @application.exception_handler(RequestValidationError)
    async def safe_validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default response includes the rejected input. Network write
        # bodies may contain plaintext credentials, so expose only safe fields.
        details = [
            {
                "loc": list(item.get("loc", ())),
                "msg": item.get("msg", "Invalid input"),
                "type": item.get("type", "value_error"),
            }
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(accounts_router)
    application.include_router(artifacts_router)
    application.include_router(content_router)
    application.include_router(delivery_router)
    application.include_router(devices_router)
    application.include_router(jobs_router)
    application.include_router(managed_apps_router)
    application.include_router(runtime_networks_router)
    application.include_router(runtimes_router)
    application.include_router(runtime_apps_router)
    application.include_router(publishing_router)
    application.include_router(redroid_provisionings_router)
    application.include_router(workflow_templates_router)
    application.include_router(workflows_router)
    return application


app = create_app()
