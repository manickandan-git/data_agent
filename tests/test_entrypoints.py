import sys
from types import SimpleNamespace
from unittest.mock import Mock

from data_agent import api, cli


def test_cli_submits_question_and_prints_answer(monkeypatch, capsys):
    workflow = Mock()
    workflow.invoke.return_value = {
        "status": "success",
        "final_answer": "There are five methods.",
    }
    monkeypatch.setattr("data_agent.agents.data_analyst.data_analyst", workflow)
    monkeypatch.setattr(cli, "configure_observability", Mock())
    monkeypatch.setattr(
        cli,
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

    assert cli.run() == 0
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
    monkeypatch.setattr("data_agent.agents.data_analyst.data_analyst", workflow)
    monkeypatch.setattr(cli, "configure_observability", Mock())
    monkeypatch.setattr(
        cli,
        "get_config",
        lambda: SimpleNamespace(
            observability_log_level="INFO",
            observability_json_logs=True,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["data-agent", "question"])

    assert cli.run() == 1


def test_api_console_entrypoint_binds_to_localhost(monkeypatch):
    run_server = Mock()
    monkeypatch.setattr("uvicorn.run", run_server)
    monkeypatch.setattr(
        api,
        "get_config",
        lambda: SimpleNamespace(
            api_host="0.0.0.0",
            api_port=9000,
            api_workers=3,
            api_reload=False,
            api_graceful_shutdown_seconds=30,
        ),
    )

    api.run()

    run_server.assert_called_once_with(
        "data_agent.api:app",
        host="0.0.0.0",
        port=9000,
        workers=3,
        reload=False,
        timeout_graceful_shutdown=30,
    )
