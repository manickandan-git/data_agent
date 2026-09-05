"""Safe workflow logging without prompt, credential, or result payloads."""

import json
import logging
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Status, StatusCode

LOGGER_NAME = "data_agent"
_tracer_provider: TracerProvider | None = None


class JsonFormatter(logging.Formatter):
    """Render workflow events as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "workflow_event", None)
        if event:
            payload.update(event)
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_observability(level: str = "INFO", *, json_logs: bool = True) -> None:
    """Configure the application logger explicitly at the process boundary."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False


def configure_telemetry(settings, application=None, *, span_exporter: SpanExporter | None = None):
    """Configure safe OTLP tracing when explicitly enabled."""
    global _tracer_provider

    if not settings.otel_enabled:
        _tracer_provider = None
        return None

    exporter = span_exporter or OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        timeout=settings.otel_export_timeout_seconds,
    )
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment.name": settings.app_environment,
            }
        ),
        sampler=TraceIdRatioBased(settings.otel_trace_sample_ratio),
    )
    processor = SimpleSpanProcessor(exporter) if span_exporter else BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    _tracer_provider = provider

    if application is not None:
        FastAPIInstrumentor.instrument_app(
            application,
            tracer_provider=provider,
            excluded_urls=settings.otel_excluded_urls,
        )
    return provider


def set_span_attribute(name: str, value: str) -> None:
    """Add a known-safe correlation attribute to the active span."""
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(name, value)


def ensure_run_id(state: Any) -> str:
    """Attach a correlation ID without inspecting or logging state payloads."""
    run_id = getattr(state, "run_id", "")
    if not run_id:
        run_id = str(uuid4())
        state.run_id = run_id
    return run_id


def log_event(
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        return
    logger.log(
        level,
        event,
        extra={"workflow_event": {"event": event, **fields}},
    )


def observed_node(workflow: str, node: str, function: Callable) -> Callable:
    """Wrap a synchronous graph node with safe lifecycle and timing events."""

    @wraps(function)
    def wrapper(state):
        run_id = ensure_run_id(state)
        started = perf_counter()
        log_event(
            logging.INFO,
            "workflow.node.started",
            workflow=workflow,
            node=node,
            run_id=run_id,
        )
        tracer = _tracer_provider.get_tracer(LOGGER_NAME) if _tracer_provider else None
        span_context = (
            tracer.start_as_current_span(
                f"{workflow}.{node}",
                record_exception=False,
                set_status_on_exception=False,
            )
            if tracer
            else nullcontext(trace.INVALID_SPAN)
        )
        with span_context as span:
            if tracer:
                span.set_attribute("data_agent.workflow", workflow)
                span.set_attribute("data_agent.node", node)
                span.set_attribute("data_agent.run_id", run_id)
            try:
                result = function(state)
            except Exception as error:
                if tracer:
                    span.set_attribute("exception.type", type(error).__name__)
                    span.set_status(Status(StatusCode.ERROR))
                log_event(
                    logging.ERROR,
                    "workflow.node.failed",
                    workflow=workflow,
                    node=node,
                    run_id=run_id,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    exception_type=type(error).__name__,
                )
                raise
        log_event(
            logging.INFO,
            "workflow.node.completed",
            workflow=workflow,
            node=node,
            run_id=run_id,
            status=getattr(result, "status", "pending"),
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        return result

    return wrapper
