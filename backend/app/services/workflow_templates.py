"""Server-owned, versioned workflow template registry."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class ContentDeliveryReviewParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_media: bool = True


class ContentDeliveryWaitReviewParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_media: bool = True
    wait_duration_seconds: int = Field(ge=1, le=86_400)


class PublishingPrepareReviewParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_media: bool = True


@dataclass(frozen=True)
class WorkflowStepSpec:
    key: str
    step_type: str
    max_attempts: int = 1


@dataclass(frozen=True)
class WorkflowTemplate:
    key: str
    version: int
    label: str
    description: str
    parameter_schema: type[BaseModel]
    steps: tuple[WorkflowStepSpec, ...]
    requires_runtime: bool = True
    requires_content: bool = True
    required_bindings: tuple[str, ...] = ("runtime_id", "content_asset_id")


CONTENT_DELIVERY_REVIEW = WorkflowTemplate(
    key="content_delivery_review",
    version=1,
    label="Content Delivery Review",
    description="Deliver one pinned content version, then wait for operator approval.",
    parameter_schema=ContentDeliveryReviewParameters,
    steps=(
        WorkflowStepSpec("deliver_content", "content.deliver"),
        WorkflowStepSpec("review_delivery", "workflow.approval"),
    ),
)
CONTENT_DELIVERY_WAIT_REVIEW = WorkflowTemplate(
    key="content_delivery_wait_review",
    version=1,
    label="Content Delivery, Wait, and Review",
    description="Deliver pinned content, wait for a bounded duration, then request approval.",
    parameter_schema=ContentDeliveryWaitReviewParameters,
    steps=(
        WorkflowStepSpec("deliver_content", "content.deliver"),
        WorkflowStepSpec("wait_after_delivery", "workflow.wait"),
        WorkflowStepSpec("review_delivery", "workflow.approval"),
    ),
)
PUBLISHING_PREPARE_REVIEW = WorkflowTemplate(
    key="publishing_prepare_review",
    version=1,
    label="Publishing Preparation Review",
    description="Verify a pinned Runtime and managed app, deliver pinned media, launch the app, and stop for operator review.",
    parameter_schema=PublishingPrepareReviewParameters,
    steps=(
        WorkflowStepSpec("verify_runtime", "publishing.verify_runtime"),
        WorkflowStepSpec("verify_app", "publishing.verify_app"),
        WorkflowStepSpec("deliver_content", "content.deliver"),
        WorkflowStepSpec("launch_app", "device.launch_app"),
        WorkflowStepSpec("verify_app_state", "publishing.verify_app_state"),
        WorkflowStepSpec("review_preparation", "workflow.approval"),
    ),
    required_bindings=(
        "account_id", "runtime_id", "content_asset_version_id",
        "managed_app_id", "managed_app_version_id",
    ),
)
_TEMPLATES = {
    (template.key, template.version): template
    for template in (CONTENT_DELIVERY_REVIEW, CONTENT_DELIVERY_WAIT_REVIEW, PUBLISHING_PREPARE_REVIEW)
}


class WorkflowTemplateError(ValueError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


def get_workflow_template(key: str, version: int | None = None) -> WorkflowTemplate:
    resolved_version = version or max((item.version for item in _TEMPLATES.values() if item.key == key), default=0)
    template = _TEMPLATES.get((key, resolved_version))
    if template is None:
        raise WorkflowTemplateError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template was not found")
    return template


def list_workflow_templates() -> tuple[WorkflowTemplate, ...]:
    return tuple(sorted(_TEMPLATES.values(), key=lambda item: (item.key, item.version)))
