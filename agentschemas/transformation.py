"""Validated, declarative instructions for dataframe transformations."""

from typing import Literal

from pydantic import BaseModel, Field

ScalarValue = str | int | float | bool | None


class FilterRule(BaseModel):
    column: str
    operator: Literal[
        "eq",
        "ne",
        "gt",
        "ge",
        "lt",
        "le",
        "in",
        "not_in",
        "contains",
        "starts_with",
        "ends_with",
        "is_null",
        "not_null",
    ]
    value: ScalarValue | list[ScalarValue] = None
    case_sensitive: bool = False


class SortRule(BaseModel):
    column: str
    ascending: bool = True


class TransformationPlan(BaseModel):
    """Operations applied in the order represented by these fields."""

    filters: list[FilterRule] = Field(default_factory=list, max_length=20)
    select_columns: list[str] | None = None
    rename_columns: dict[str, str] = Field(default_factory=dict)
    drop_duplicates_on: list[str] | None = None
    sort: list[SortRule] = Field(default_factory=list, max_length=10)
    limit: int | None = Field(default=None, ge=1, le=100_000)
