import ast
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_agents_package_does_not_eagerly_import_workflows():
    script = (
        "import sys; import agents; "
        "assert 'agents.data_analyst' not in sys.modules; "
        "assert 'agents.etl_analyst' not in sys.modules; "
        "assert 'agents.sql_analyst' not in sys.modules"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module_path",
    [
        "agents/data_analyst.py",
        "agents/etl_analyst.py",
        "agents/sql_analyst.py",
    ],
)
def test_agent_imports_do_not_mutate_python_path(module_path):
    tree = ast.parse((PROJECT_ROOT / module_path).read_text(encoding="utf-8"))

    mutations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
        and node.func.value.attr == "path"
        and node.func.attr in {"append", "extend", "insert", "remove", "pop"}
    ]

    assert mutations == []
