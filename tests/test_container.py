from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_uses_locked_multistage_non_root_runtime():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert " AS builder" in dockerfile
    assert " AS runtime" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "/health/live" in dockerfile
    assert 'CMD ["data-agent-api"]' in dockerfile
    assert "COPY . ." not in dockerfile


def test_dockerignore_excludes_credentials_and_local_artifacts():
    ignored = set((PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())

    assert {".env", ".env.*", ".git", ".venv", "tests"} <= ignored
    assert "data/extract" in ignored
    assert "data/transform" in ignored
