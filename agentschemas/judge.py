"""Schema definition for the Judge agent."""

from typing import Literal

from pydantic import BaseModel, Field


class JudgeSchema(BaseModel):
    answer: Literal["Yes", "No"] = Field(
        ..., description="Indicates whether the generated SQL query is safe to execute or not"
    )
    comments: str = Field(
        ..., description="Additional comments or feedback from the judge regarding the SQL query"
    )
