"""HTTP interface for the Data Agent workflows."""

from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from data_agent.agentschemas.workflow import WorkflowStatus
from data_agent.config import get_config
from data_agent.utils.api_security import (
    APIKeyAuthenticator,
    ConcurrencyLimiter,
    SlidingWindowRateLimiter,
)
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


async def _database_readiness(settings) -> None:
    database_url = settings.require_database_url().replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    connection = await asyncpg.connect(
        database_url,
        timeout=settings.api_readiness_timeout_seconds,
    )
    try:
        await connection.fetchval(
            "SELECT 1",
            timeout=settings.api_readiness_timeout_seconds,
        )
    finally:
        await connection.close(timeout=settings.api_readiness_timeout_seconds)


def create_app(
    workflow=None,
    settings=None,
    *,
    span_exporter=None,
    metric_reader=None,
    readiness_check=None,
) -> FastAPI:
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
        _app.state.accepting_requests = True
        try:
            yield
        finally:
            _app.state.accepting_requests = False
            await _app.state.concurrency_limiter.wait_for_idle(
                active_settings.api_graceful_shutdown_seconds
            )
            if telemetry_provider is not None:
                telemetry_provider.shutdown()

    active_settings = current_settings()
    application = FastAPI(
        title="Data Agent API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if current_settings().api_docs_enabled else None,
        redoc_url="/redoc" if current_settings().api_docs_enabled else None,
        openapi_url="/openapi.json" if current_settings().api_docs_enabled else None,
    )
    application.state.telemetry_provider = configure_telemetry(
        active_settings,
        application,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )
    authenticator = APIKeyAuthenticator(active_settings.configured_api_keys())
    rate_limiter = SlidingWindowRateLimiter(
        active_settings.api_rate_limit_requests,
        active_settings.api_rate_limit_window_seconds,
    )
    concurrency_limiter = ConcurrencyLimiter(active_settings.api_max_concurrent_requests)
    application.state.concurrency_limiter = concurrency_limiter
    application.state.accepting_requests = False
    bearer = HTTPBearer(auto_error=False)

    async def authorize_and_limit(
        credentials: HTTPAuthorizationCredentials | None = Security(bearer),
    ) -> str:
        if active_settings.api_auth_enabled:
            if credentials is None or credentials.scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Valid bearer authentication is required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            client_id = authenticator.authenticate(credentials.credentials)
            if client_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Valid bearer authentication is required.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            client_id = "anonymous"

        allowed, retry_after = await rate_limiter.allow(client_id)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Request rate limit exceeded.",
                headers={"Retry-After": str(retry_after)},
            )
        return client_id

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

    @application.get("/health/live", response_model=HealthResponse)
    async def health_live() -> HealthResponse:
        return HealthResponse()

    @application.get("/health/ready", response_model=HealthResponse)
    async def health_ready(request: Request) -> HealthResponse:
        if not request.app.state.accepting_requests:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The service is not ready.",
            )
        if active_settings.api_readiness_database_enabled:
            check = readiness_check or _database_readiness
            try:
                await check(active_settings)
            except (asyncpg.PostgresError, OSError, TimeoutError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The service is not ready.",
                ) from None
        return HealthResponse()

    @application.post("/api/v1/query", response_model=QueryResponse)
    async def query(
        payload: QueryRequest,
        request: Request,
        raw_response: Response,
        _client_id: str = Depends(authorize_and_limit),
    ) -> QueryResponse:
        run_id = str(uuid4())
        set_span_attribute("data_agent.run_id", run_id)
        active_workflow = workflow or _default_workflow()
        if not await concurrency_limiter.try_acquire():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The service is at its workflow concurrency limit.",
                headers={"Retry-After": "1"},
            )
        try:
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
        finally:
            await concurrency_limiter.release()

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
        timeout_graceful_shutdown=settings.api_graceful_shutdown_seconds,
    )
