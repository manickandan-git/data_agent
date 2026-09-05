import sys
from types import SimpleNamespace
from unittest.mock import Mock

import api
import main


def test_cli_submits_question_and_prints_answer(monkeypatch, capsys):
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "success",
        "final_answer": "There are five methods.",
    }
    monkeypatch.setattr("agents.data_analyst.data_analyst", workflow)
    monkeypatch.setattr(main, "configure_observability", Mock())
    monkeypatch.setattr(
        main,
        "get_config",
        lambda: SimpleNamespace(
            observability_log_level="INFO",
            observability_json_logs=True,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["data-agent", "What payment methods are available?"],
    )

    assert main.run() == 0
    assert capsys.readouterr().out.strip() == "There are five methods."
    assert (
        workflow.invoke.call_args.args[0]["messages"][0].content
        == "What payment methods are available?"
    )


def test_cli_returns_nonzero_for_workflow_error(monkeypatch):
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "error",
        "final_answer": "Request failed.",
    }
    monkeypatch.setattr("agents.data_analyst.data_analyst", workflow)
    monkeypatch.setattr(main, "configure_observability", Mock())
    monkeypatch.setattr(
        main,
        "get_config",
        lambda: SimpleNamespace(
            observability_log_level="INFO",
            observability_json_logs=True,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["data-agent", "question"])

    assert main.run() == 1


def test_api_console_entrypoint_binds_to_localhost(monkeypatch):
    run_server = Mock()
    monkeypatch.setattr("uvicorn.run", run_server)

    api.run()

    run_server.assert_called_once_with(
        "api:app",
        host="127.0.0.1",
        port=8000,
    )
