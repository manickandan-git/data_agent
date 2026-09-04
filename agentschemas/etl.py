"""ETL (Extract, Transform, Load) Agent Schema module."""


from pydantic import Field

from agentschemas.workflow import WorkflowOutput


class ETLSchema(WorkflowOutput):
    """Schema for ETL (Extract, Transform, Load) agent."""

    messages: list = Field(..., description="Conversation snapshot for the ETL agent")
