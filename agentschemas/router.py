from typing import Literal

from pydantic import BaseModel, Field


class RouterSchema(BaseModel):
    answer: Literal["sql","etl"] = Field(..., description="Indicates whether the user's question is related to SQL or ETL operations")
    comments: str = Field(..., description="Additional comments or feedback regarding the classification of the user's question")