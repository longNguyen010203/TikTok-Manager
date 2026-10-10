"""Built-in job handlers and default registry construction."""

from __future__ import annotations

from typing import Any

from worker.registry import HandlerRegistry, JobExecutionContext


def echo(context: JobExecutionContext) -> Any:
    """Return the supplied payload unchanged."""
    return context.payload


def execute_backend_job(context: JobExecutionContext) -> Any:
    """Ask the backend to execute a registered typed Job."""
    return context.backend_client.execute_job(
        context.job_id, context.claim_token, context.attempt
    )


def create_default_registry() -> HandlerRegistry:
    """Create the registry used by the command-line worker."""
    registry = HandlerRegistry()
    registry.register("echo", echo)
    for job_type in (
        "device.screenshot", "device.package_state", "device.launch_app",
        "device.stop_app", "device.push_file", "device.pull_file",
        "device.import_media",
    ):
        registry.register(job_type, execute_backend_job)
    registry.register("content.inspect", execute_backend_job)
    registry.register("content.thumbnail", execute_backend_job)
    registry.register("content.deliver", execute_backend_job)
    registry.register("app.inspect", execute_backend_job)
    registry.register("app.install", execute_backend_job)
    registry.register("app.verify", execute_backend_job)
    registry.register("publishing.verify_runtime", execute_backend_job)
    registry.register("publishing.verify_app", execute_backend_job)
    registry.register("publishing.verify_app_state", execute_backend_job)
    registry.register("tiktok.detect_screen", execute_backend_job)
    registry.register("tiktok.open_create", execute_backend_job)
    registry.register("tiktok.open_media_picker", execute_backend_job)
    registry.register("tiktok.select_media", execute_backend_job)
    registry.register("tiktok.open_caption", execute_backend_job)
    registry.register("tiktok.skip_interests", execute_backend_job)
    registry.register("tiktok.open_profile", execute_backend_job)
    registry.register("tiktok.choose_email_signup", execute_backend_job)
    registry.register("tiktok.set_registration_email", execute_backend_job)
    registry.register("tiktok.continue_registration_email", execute_backend_job)
    registry.register("tiktok.set_caption", execute_backend_job)
    registry.register("tiktok.set_post_options", execute_backend_job)
    registry.register("tiktok.prepare_publish", execute_backend_job)
    return registry
