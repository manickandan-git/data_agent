"""Safe workflow logging without prompt, credential, or result payloads."""

import json
import logging
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Status, StatusCode

LOGGER_NAME = "data_agent"
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_operation_counter = None
_operation_duration = None
_value_histogram = None


@dataclass
class TelemetryRuntime:
    tracer_provider: TracerProvider
    meter_provider: MeterProvider

    def get_tracer(self, name: str):
        return self.tracer_provider.get_tracer(name)

    def force_flush(self) -> None:
        self.tracer_provider.force_flush()
        self.meter_provider.force_flush()

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()


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


def _metrics_endpoint(settings) -> str:
    if settings.otel_metrics_exporter_endpoint:
        return settings.otel_metrics_exporter_endpoint
    return settings.otel_exporter_endpoint.removesuffix("/v1/traces") + "/v1/metrics"


def configure_telemetry(
    settings,
    application=None,
    *,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
):
    """Configure safe OTLP tracing when explicitly enabled."""
    global _meter_provider, _operation_counter, _operation_duration, _tracer_provider
    global _value_histogram

    if not settings.otel_enabled:
        _tracer_provider = None
        _meter_provider = None
        _operation_counter = None
        _operation_duration = None
        _value_histogram = None
        return None

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment.name": settings.app_environment,
        }
    )
    exporter = span_exporter or OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        timeout=settings.otel_export_timeout_seconds,
    )
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.otel_trace_sample_ratio),
    )
    processor = SimpleSpanProcessor(exporter) if span_exporter else BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    _tracer_provider = provider

    if metric_reader is None:
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=_metrics_endpoint(settings),
                timeout=settings.otel_export_timeout_seconds,
            ),
            export_interval_millis=int(settings.otel_metric_export_interval_seconds * 1000),
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    _meter_provider = meter_provider
    meter = meter_provider.get_meter(LOGGER_NAME)
    _operation_counter = meter.create_counter(
        "data_agent.operation.count",
        description="Completed application operations",
    )
    _operation_duration = meter.create_histogram(
        "data_agent.operation.duration",
        unit="ms",
        description="Application operation duration",
    )
    _value_histogram = meter.create_histogram(
        "data_agent.operation.value",
        unit="{item}",
        description="Bounded operational item counts",
    )

    if application is not None:
        FastAPIInstrumentor.instrument_app(
            application,
            tracer_provider=provider,
            meter_provider=meter_provider,
            excluded_urls=settings.otel_excluded_urls,
        )
    return TelemetryRuntime(provider, meter_provider)


def record_operation(
    operation: str,
    duration_ms: float,
    *,
    outcome: str,
    attributes: dict[str, str] | None = None,
) -> None:
    """Record bounded operational metrics without accepting payload values."""
    if _operation_counter is None or _operation_duration is None:
        return
    fields = {"operation": operation, "outcome": outcome, **(attributes or {})}
    _operation_counter.add(1, fields)
    _operation_duration.record(duration_ms, fields)


def record_value(operation: str, value: int, *, kind: str, attributes=None) -> None:
    """Record a non-negative operational count such as rows, pages, or tokens."""
    if _value_histogram is None:
        return
    _value_histogram.record(
        max(0, value),
        {"operation": operation, "value.kind": kind, **(attributes or {})},
    )


def start_operation_span(name: str, attributes: dict[str, str] | None = None):
    """Start a span whose caller supplies only reviewed operational attributes."""
    if _tracer_provider is None:
        return nullcontext(trace.INVALID_SPAN)
    return _tracer_provider.get_tracer(LOGGER_NAME).start_as_current_span(
        name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    )


def observed_operation(
    name: str,
    *,
    attributes: dict[str, str] | None = None,
    failure_when: Callable[[Any], bool] | None = None,
):
    """Instrument a synchronous operation without examining its arguments or result."""

    def decorator(function: Callable) -> Callable:
        @wraps(function)
        def wrapper(*args, **kwargs):
            started = perf_counter()
            with start_operation_span(name, attributes) as span:
                try:
                    result = function(*args, **kwargs)
                except Exception as error:
                    duration_ms = (perf_counter() - started) * 1000
                    if span.is_recording():
                        span.set_attribute("exception.type", type(error).__name__)
                        span.set_status(Status(StatusCode.ERROR))
                    record_operation(name, duration_ms, outcome="error", attributes=attributes)
                    raise
                failed = failure_when(result) if failure_when else False
                if failed and span.is_recording():
                    span.set_status(Status(StatusCode.ERROR))
                record_operation(
                    name,
                    (perf_counter() - started) * 1000,
                    outcome="error" if failed else "success",
                    attributes=attributes,
                )
            return result

        return wrapper

    return decorator


def observed_async_operation(
    name: str,
    *,
    attributes: dict[str, str] | None = None,
    failure_when: Callable[[Any], bool] | None = None,
):
    """Instrument an async operation without examining its arguments or result."""

    def decorator(function: Callable) -> Callable:
        @wraps(function)
        async def wrapper(*args, **kwargs):
            started = perf_counter()
            with start_operation_span(name, attributes) as span:
                try:
                    result = await function(*args, **kwargs)
                except Exception as error:
                    duration_ms = (perf_counter() - started) * 1000
                    if span.is_recording():
                        span.set_attribute("exception.type", type(error).__name__)
                        span.set_status(Status(StatusCode.ERROR))
                    record_operation(name, duration_ms, outcome="error", attributes=attributes)
                    raise
                failed = failure_when(result) if failure_when else False
                if failed and span.is_recording():
                    span.set_status(Status(StatusCode.ERROR))
                record_operation(
                    name,
                    (perf_counter() - started) * 1000,
                    outcome="error" if failed else "success",
                    attributes=attributes,
                )
            return result

        return wrapper

    return decorator


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
                duration_ms = round((perf_counter() - started) * 1000, 2)
                if tracer:
                    span.set_attribute("exception.type", type(error).__name__)
                    span.set_status(Status(StatusCode.ERROR))
                log_event(
                    logging.ERROR,
                    "workflow.node.failed",
                    workflow=workflow,
                    node=node,
                    run_id=run_id,
                    duration_ms=duration_ms,
                    exception_type=type(error).__name__,
                )
                record_operation(
                    "workflow.node",
                    duration_ms,
                    outcome="error",
                    attributes={"workflow": workflow, "node": node},
                )
                raise
        duration_ms = round((perf_counter() - started) * 1000, 2)
        log_event(
            logging.INFO,
            "workflow.node.completed",
            workflow=workflow,
            node=node,
            run_id=run_id,
            status=getattr(result, "status", "pending"),
            duration_ms=duration_ms,
        )
        record_operation(
            "workflow.node",
            duration_ms,
            outcome="success",
            attributes={"workflow": workflow, "node": node},
        )
        return result

    return wrapper
