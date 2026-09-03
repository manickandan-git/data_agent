from operator import add
from typing import Annotated

from pydantic import BaseModel, Field


class DataSchema(BaseModel):
    messages : Annotated[list,add] = Field(..., description="List of messages to be processed by the Data agent")
    route_response : str = Field(default="", description="The response from the router indicating whether to route to SQL or ETL operations")