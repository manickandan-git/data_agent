"""HTTP interface for the Data Agent workflows."""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from data_agent.agentschemas.workflow import WorkflowStatus
from data_agent.config import get_config
from data_agent.utils.observability import (
    configure_observability,
    configure_telemetry,
    set_span_attribute,
)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4_000)


class QueryResponse(BaseModel):
    run_id: str
    status: WorkflowStatus
    route: str
    final_answer: str
    workflow_error: str


class HealthResponse(BaseModel):
    status: str = "ok"


def _default_workflow():
    from data_agent.agents.data_analyst import data_analyst

    return data_analyst


def create_app(workflow=None, settings=None, *, span_exporter=None) -> FastAPI:
    """Build an API app; an injected workflow keeps endpoint tests offline."""

    def current_settings():
        return settings or get_config()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        active_settings = current_settings()
        configure_observability(
            active_settings.observability_log_level,
            json_logs=active_settings.observability_json_logs,
        )
        telemetry_provider = getattr(_app.state, "telemetry_provider", None)
        try:
            yield
        finally:
            if telemetry_provider is not None:
                telemetry_provider.shutdown()

    application = FastAPI(
        title="Data Agent API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if current_settings().api_docs_enabled else None,
        redoc_url="/redoc" if current_settings().api_docs_enabled else None,
        openapi_url="/openapi.json" if current_settings().api_docs_enabled else None,
    )
    application.state.telemetry_provider = configure_telemetry(
        current_settings(),
        application,
        span_exporter=span_exporter,
    )

    @application.middleware("http")
    async def limit_request_size(request: Request, call_next):
        max_bytes = current_settings().api_max_request_bytes
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > max_bytes
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body is too large."},
                )
        body = await request.body()
        if len(body) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body is too large."},
            )
        return await call_next(request)

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @application.post("/api/v1/query", response_model=QueryResponse)
    async def query(
        payload: QueryRequest,
        request: Request,
        raw_response: Response,
    ) -> QueryResponse:
        run_id = str(uuid4())
        set_span_attribute("data_agent.run_id", run_id)
        active_workflow = workflow or _default_workflow()
        try:
            result = await run_in_threadpool(
                active_workflow.invoke,
                {
                    "messages": [HumanMessage(content=payload.question)],
                    "run_id": run_id,
                },
            )
        except (RuntimeError, ValueError, TypeError):
            result = {
                "run_id": run_id,
                "status": "error",
                "route_response": "",
                "final_answer": "The request could not be processed.",
                "workflow_error": "The request could not be processed.",
            }

        response = QueryResponse(
            run_id=result.get("run_id") or run_id,
            status=result.get("status", "error"),
            route=result.get("route_response", ""),
            final_answer=result.get("final_answer", ""),
            workflow_error=result.get("workflow_error", ""),
        )
        request.state.run_id = response.run_id
        raw_response.headers["X-Request-ID"] = response.run_id
        if response.status == "error":
            raw_response.status_code = 500
        return response

    return application


app = create_app()


def run() -> None:
    """Run the local API server through the installed console command."""
    import uvicorn

    settings = get_config()
    uvicorn.run(
        "data_agent.api:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.api_reload,
    )
