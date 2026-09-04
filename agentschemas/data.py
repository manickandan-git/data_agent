from pydantic import Field

from agentschemas.workflow import WorkflowOutput


class DataSchema(WorkflowOutput):
    messages: list = Field(..., description="Conversation snapshot for the data agent")
    route_response: str = Field(
        default="",
        description="The selected workflow.",
    )
