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
_TEMPLATES = {
    (template.key, template.version): template
    for template in (CONTENT_DELIVERY_REVIEW, CONTENT_DELIVERY_WAIT_REVIEW)
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
