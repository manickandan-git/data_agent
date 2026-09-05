"""Schema-aware question review, before any SQL is generated."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QuestionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["clear", "ambiguous", "unsupported"]
    message: str = Field(
        min_length=1,
        description=(
            "For clear questions, explain why the schema can answer the original request. "
            "For ambiguity, ask a specific clarification question. For unsupported "
            "requests, explain the missing data. Do not invent assumptions."
        ),
    )
