"""Common output contract for every workflow."""

from typing import Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal[
    "pending",
    "success",
    "needs_clarification",
    "rejected",
    "error",
]


class WorkflowOutput(BaseModel):
    """Fields callers can rely on regardless of the selected workflow."""

    status: WorkflowStatus = "pending"
    final_answer: str = Field(
        default="",
        description="User-facing result, clarification, rejection, or error message.",
    )
    workflow_error: str = Field(
        default="",
        description="Safe diagnostic message when status is error.",
    )
