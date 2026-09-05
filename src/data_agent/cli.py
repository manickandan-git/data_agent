"""Command-line interface for one Data Agent question."""

import argparse

from langchain_core.messages import HumanMessage

from data_agent.config import get_config
from data_agent.utils.observability import configure_observability


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-agent",
        description="Route one natural-language request through the Data Agent.",
    )
    parser.add_argument("question", help="Database or ETL request to process.")
    return parser


def run() -> int:
    """Run one workflow request and print only its public final answer."""
    args = build_parser().parse_args()
    settings = get_config()
    configure_observability(
        settings.observability_log_level,
        json_logs=settings.observability_json_logs,
    )

    from data_agent.agents.data_analyst import data_analyst

    result = data_analyst.invoke({"messages": [HumanMessage(content=args.question)]})
    print(result["final_answer"])
    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(run())
