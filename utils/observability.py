"""Safe workflow logging without prompt, credential, or result payloads."""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any
from uuid import uuid4

LOGGER_NAME = "data_agent"


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
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_observability(level: str = "INFO", *, json_logs: bool = True) -> None:
    """Configure the application logger explicitly at the process boundary."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False


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
        try:
            result = function(state)
        except Exception as error:
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
