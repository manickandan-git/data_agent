"""ETL (Extract, Transform, Load) Agent Schema module."""


from operator import add
from typing import Annotated

from pydantic import BaseModel, Field


class ETLSchema(BaseModel):
    """Schema for ETL (Extract, Transform, Load) agent."""

    messages : Annotated[list,add] = Field(..., description="List of messages to be processed by the ETL agent")
