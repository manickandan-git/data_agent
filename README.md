# Data Agent

Data Agent is a LangGraph application that routes natural-language requests to
an SQL analyst for PostgreSQL questions or an ETL analyst for JSON API
extraction and local dataset transformation.

It uses LangChain-compatible chat models, Pydantic structured outputs,
SQLAlchemy models, Alembic migrations, and pandas-based ETL operations.

Product requirements and engineering designs are maintained in the
[`docs`](docs/README.md) directory.

## Features

- LLM routing between SQL and ETL workflows.
- OpenAI and Anthropic support, with an adapter interface for other providers.
- Question validation and clarification before SQL generation.
- Exact categorical-value grounding from database metadata.
- Deterministic read-only SQL validation plus an LLM relevance review.
- Read-only PostgreSQL execution with a configurable timeout.
- Bounded HTTPS JSON extraction with pagination and retries.
- Declarative data transformations without executing generated code.
- File access restricted to the project `data` directories.
- Tested ORM relationships for users, vehicles, rides, payments, and ratings.
- Offline tests for configuration, models, schemas, SQL, and ETL behavior.

## Requirements

- Python 3.13 or newer.
- PostgreSQL for database questions and migrations.
- An API key for the selected LLM provider.
- Docker with Compose v2 when running the production-style local stack.

## Installation

Install the application and its console commands from a source checkout:

```powershell
uv sync --dev
.venv\Scripts\Activate.ps1
```

For a runtime-only editable installation with pip:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

`pyproject.toml` and `uv.lock` are the primary project and lock files.
`requirements.txt` is a pinned pip-compatible environment for reproducible
source-checkout development.

### Build distributions

Build a wheel and source distribution:

```powershell
uv build
```

The artifacts are written to `dist/`. Packaging metadata explicitly includes
the application modules and the `agents`, `agentschemas`, `models`,
`schemas`, and `utils` packages. The source distribution also includes the
README, environment template, Alembic configuration, and migration sources.

Database seed CSV files intentionally remain repository data rather than wheel
package data. Run seed migrations from a source checkout where `data/*.csv`
is present.

## Configuration

Copy `.env.example` to `.env`. Configuration is loaded from the repository
directory regardless of the current working directory. Never commit real API
keys, database credentials, or bearer tokens.

### Environment profiles

Set `APP_ENVIRONMENT` to `development`, `test`, `staging`, or `production`.
The application first reads `.env` and then `.env.<environment>`, so a profile
file can override shared settings. Operating-system environment variables take
precedence over both files and should be used for deployed secrets.

For example, keep shared non-secret defaults in `.env`, staging overrides in
`.env.staging`, and configure the deployment with:

```dotenv
APP_ENVIRONMENT=staging
```

Do not commit `.env` or `.env.<environment>` files containing secrets. The
`test` profile is intended for automated tests, not for weakening validation.

### Configuration reference

All names below are optional unless a requirement is noted. Values shown are
the application defaults. Pydantic reads names case-insensitively from the
process environment, `.env`, and the selected `.env.<environment>` profile.

| Setting | Default | Purpose and validation |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | One of `development`, `test`, `staging`, or `production` |
| `LLM_PROVIDER` | `openai` | Registered LLM provider name |
| `LLM_MODEL_LOW` | provider default | Optional low-complexity model override |
| `LLM_MODEL_MEDIUM` | provider default | Optional medium-complexity model override |
| `LLM_MODEL_HIGH` | provider default | Optional high-complexity model override |
| `LLM_TEMPERATURE` | `0` | From `0` through `1` |
| `LLM_TIMEOUT_SECONDS` | `60` | Positive provider request timeout |
| `LLM_MAX_RETRIES` | `2` | From `0` through `10` |
| `LLM_MAX_TOKENS` | `4096` | Positive output-token limit |
| `OPENAI_REASONING_EFFORT` | `low` | `none`, `low`, `medium`, `high`, `xhigh`, or `max` |
| `OPENAI_API_KEY` | unset | Required when an OpenAI request is made |
| `ANTHROPIC_API_KEY` | unset | Required when an Anthropic request is made |
| `OPENAI_BASE_URL` | unset | Optional trusted OpenAI-compatible endpoint |

| Setting | Default | Purpose and validation |
| --- | --- | --- |
| `OBSERVABILITY_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR`; production rejects `DEBUG` |
| `OBSERVABILITY_JSON_LOGS` | `true` | Emit structured JSON instead of console text |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing and metrics |
| `OTEL_SERVICE_NAME` | `data-agent` | Telemetry service name, 1–128 characters |
| `OTEL_EXPORTER_ENDPOINT` | unset | Required trace endpoint when telemetry is enabled |
| `OTEL_METRICS_EXPORTER_ENDPOINT` | derived | Optional metrics endpoint; otherwise derived from the trace endpoint |
| `OTEL_EXPORT_TIMEOUT_SECONDS` | `10` | Positive value, at most `60` seconds |
| `OTEL_METRIC_EXPORT_INTERVAL_SECONDS` | `60` | From `5` through `300` seconds |
| `OTEL_TRACE_SAMPLE_RATIO` | `1` | Trace fraction from `0` through `1` |
| `OTEL_EXCLUDED_URLS` | `/health` | FastAPI instrumentation exclusion pattern |

| Setting | Default | Purpose and validation |
| --- | --- | --- |
| `API_HOST` | `127.0.0.1` | Bind address |
| `API_PORT` | `8000` | From `1` through `65535` |
| `API_WORKERS` | `1` | From `1` through `32` |
| `API_RELOAD` | `false` | Requires one worker; forbidden in staging and production |
| `API_DOCS_ENABLED` | environment-dependent | Enabled except in production unless explicitly overridden |
| `API_AUTH_ENABLED` | environment-dependent | Enabled and mandatory in production; disabled elsewhere by default |
| `API_KEYS` | unset | Comma-separated bearer keys; each must have at least 32 characters when authentication is enabled |
| `API_RATE_LIMIT_REQUESTS` | `60` | Per-key requests per window, from `1` through `100000` |
| `API_RATE_LIMIT_WINDOW_SECONDS` | `60` | From `1` through `3600` seconds |
| `API_MAX_CONCURRENT_REQUESTS` | `4` | Process-local workflow limit, from `1` through `1000` |
| `API_GRACEFUL_SHUTDOWN_SECONDS` | `30` | Drain timeout, from `1` through `300` seconds |
| `API_READINESS_DATABASE_ENABLED` | `false` | Include PostgreSQL in readiness; requires `DATABASE_URL` |
| `API_READINESS_TIMEOUT_SECONDS` | `3` | Positive readiness timeout, at most `30` seconds |
| `API_MAX_REQUEST_BYTES` | `16384` | Request-body limit, from `1024` through `1048576` bytes |

| Setting | Default | Purpose and validation |
| --- | --- | --- |
| `DATABASE_URL` | unset | PostgreSQL URL; required for SQL operations and optional database readiness |
| `DATABASE_SCHEMA` | `public` | SQL identifier used for schema discovery |
| `SQL_ROW_LIMIT` | `10` | Prompted result limit, from `1` through `100000` |
| `SQL_TIMEOUT_SECONDS` | `30` | Execution timeout, positive and at most `300` seconds |
| `SQL_CATEGORICAL_COLUMNS` | documented below | JSON object containing validated table and column identifiers |
| `SQL_CATEGORICAL_VALUE_LIMIT` | `50` | Distinct values per configured column, from `1` through `200` |
| `ETL_TIMEOUT_SECONDS` | `30` | HTTP timeout, positive and at most `120` seconds |
| `ETL_MAX_RETRIES` | `2` | From `0` through `5` |
| `ETL_MAX_PAGES` | `20` | From `1` through `100` |
| `ETL_MAX_ROWS` | `100000` | From `1` through `1000000` |
| `ETL_AUTH_ORIGIN` | empty | Exact allowed HTTPS origin for ETL bearer authentication |
| `ETL_BEARER_TOKEN` | unset | Optional ETL source bearer credential |

The API server is configured with `API_HOST`, `API_PORT`, `API_WORKERS`, and
`API_RELOAD`. Reload cannot be combined with multiple workers and is rejected
in staging and production. Production also rejects debug logging and disables
the interactive `/docs`, `/redoc`, and `/openapi.json` routes by default. Set
`API_DOCS_ENABLED=true` only when those routes are intentionally exposed behind
appropriate access controls.

### LLM providers

OpenAI is the default:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
```

Empty model settings select these defaults:

| Work level | OpenAI model |
| --- | --- |
| Low | `gpt-5.6-luna` |
| Medium | `gpt-5.6-terra` |
| High | `gpt-5.6-sol` |

For Anthropic, provide explicit model IDs supported by your account:

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
LLM_MODEL_LOW=your-low-model
LLM_MODEL_MEDIUM=your-medium-model
LLM_MODEL_HIGH=your-high-model
```

Models must support tool calling and structured output. Other providers can
register a `ProviderAdapter` through `register_provider()` in
`src/data_agent/utils/llm_pick.py`; workflows do not require
provider-specific edits.

Request controls include `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`,
`LLM_MAX_RETRIES`, `LLM_MAX_TOKENS`, and `OPENAI_REASONING_EFFORT`.
The default GPT-5.6 models use the Responses API and reasoning effort without
temperature. Legacy or custom OpenAI overrides retain chat parameters.
`OPENAI_BASE_URL` must point only to a trusted compatible endpoint because it
receives the configured key and prompts.

Clients and settings are cached. Restart after editing `.env`, or call
`reset_llm_clients()` to clear both caches.

### Observability

The application entry point enables structured workflow logs using:

```dotenv
OBSERVABILITY_LOG_LEVEL=INFO
OBSERVABILITY_JSON_LOGS=true
```

Each workflow result has a `run_id`, and routed SQL or ETL work retains that
same correlation ID. Graph nodes emit `workflow.node.started`,
`workflow.node.completed`, or `workflow.node.failed` events with the
workflow name, node name, status, and duration in milliseconds.

Logging is not configured during import. Applications invoking graphs directly
can enable it explicitly:

```python
from data_agent.utils.observability import configure_observability

configure_observability("INFO", json_logs=True)
```

Observability events intentionally exclude prompts, generated SQL, database
results, source records, URLs, credentials, and exception messages. Failed-node
events record only the exception type.

OpenTelemetry tracing is disabled by default. To send traces to an OTLP HTTP
collector, configure its `/v1/traces` endpoint:

```dotenv
OTEL_ENABLED=true
OTEL_SERVICE_NAME=data-agent
OTEL_EXPORTER_ENDPOINT=http://localhost:4318/v1/traces
OTEL_METRICS_EXPORTER_ENDPOINT=http://localhost:4318/v1/metrics
OTEL_EXPORT_TIMEOUT_SECONDS=10
OTEL_METRIC_EXPORT_INTERVAL_SECONDS=60
OTEL_TRACE_SAMPLE_RATIO=1
OTEL_EXCLUDED_URLS=/health
```

API requests and workflow nodes then participate in the same distributed trace.
JSON logs emitted inside a sampled span include `trace_id` and `span_id`, while
workflow spans carry the safe `run_id` correlation attribute. Health checks are
excluded by default to reduce noise. `OTEL_EXCLUDED_URLS` accepts the URL pattern
syntax supported by the OpenTelemetry FastAPI instrumentation.

Use a sample ratio below `1` for high-volume production services. Send telemetry
to an OpenTelemetry Collector rather than embedding vendor credentials in code;
standard exporter environment variables such as `OTEL_EXPORTER_OTLP_HEADERS`
can supply collector authentication. Tracing never adds prompts, generated SQL,
query results, extracted records, credentials, full URLs, or exception messages
as custom span attributes.

The application exports standard FastAPI HTTP server metrics plus these bounded
custom instruments:

| Instrument | Meaning |
| --- | --- |
| `data_agent.operation.count` | Completed operations grouped by operation and outcome |
| `data_agent.operation.duration` | LLM, SQL, ETL, and workflow latency in milliseconds |
| `data_agent.operation.value` | Token, row, page, and retry counts |

Operational dimensions include workflow/node names, LLM provider/model and
difficulty, SQL operation type, ETL stage, outcome, and value kind. They never
include prompts, responses, SQL text, URLs, file paths, database results, or
records. LLM token metrics are emitted only when the selected provider returns
usage metadata. If `OTEL_METRICS_EXPORTER_ENDPOINT` is omitted, the application
derives it by replacing `/v1/traces` in the trace endpoint with `/v1/metrics`.

### Database and SQL

`DATABASE_URL` is needed only for database operations:

```dotenv
DATABASE_URL=postgresql://user:password@localhost:5432/data_agent
DATABASE_SCHEMA=public
SQL_ROW_LIMIT=10
SQL_TIMEOUT_SECONDS=30
```

`SQL_ROW_LIMIT` instructs the generator; it is not a database-enforced cap.
`SQL_TIMEOUT_SECONDS` is enforced during execution. Existing ORM models and
migrations target `public`; changing `DATABASE_SCHEMA` changes discovery but
does not relocate those objects.

#### Categorical value grounding

Schema discovery retrieves bounded distinct values for this explicit allowlist:

```dotenv
SQL_CATEGORICAL_COLUMNS={"payments":["payment_method","payment_status"],"ratings":["rating"],"rides":["status","cancellation_reason"],"users":["user_type","city","province","is_active"],"vehicles":["make","model","color","is_active"]}
SQL_CATEGORICAL_VALUE_LIMIT=50
```

This maps natural wording to exact stored literals—for example, “credit card”
to `credit_card`—without exposing full sample records. Keep the allowlist
limited to non-sensitive, low-cardinality fields. Never add names, emails,
phones, comments, identifiers, license plates, or free text.

If a column exceeds `SQL_CATEGORICAL_VALUE_LIMIT`, its metadata may be
incomplete. The workflow should clarify rather than assume an unlisted value is
invalid.

### ETL

```dotenv
ETL_TIMEOUT_SECONDS=30
ETL_MAX_RETRIES=2
ETL_MAX_PAGES=20
ETL_MAX_ROWS=100000
ETL_AUTH_ORIGIN=
ETL_BEARER_TOKEN=
```

Bearer credentials are sent only when `ETL_AUTH_ORIGIN` exactly matches the
HTTPS request origin. Redirects, embedded credentials, cross-origin pagination,
pagination cycles, environment proxies, and `.netrc` credentials are rejected
or disabled. Errors omit response bodies and URLs.

Extraction accepts JSON arrays of objects. Dotted paths such as `data.items`
and `links.next` select records and pagination; defaults are `results` and
`next`. An empty next path disables pagination. Outputs may be CSV,
newline-delimited JSON, or Parquet.

Extraction output is confined to `data/extract`. Transformation input must be
inside `data`, and output is confined to `data/transform`. Existing output
files are never overwritten.

Validated transformation plans support filtering, column selection, renaming,
duplicate removal, sorting, and row limits. Generated Python, SQL, shell
commands, arbitrary expressions, and arbitrary file operations are not run.

## Usage

### HTTP API

The `/health` endpoint is public so load balancers can check the process. The
`/api/v1/query` endpoint supports bearer API-key authentication, per-key rate
limits, and a process-wide workflow concurrency limit:

```dotenv
API_AUTH_ENABLED=true
API_KEYS=replace-with-at-least-32-random-characters
API_RATE_LIMIT_REQUESTS=60
API_RATE_LIMIT_WINDOW_SECONDS=60
API_MAX_CONCURRENT_REQUESTS=4
```

Send a configured key in the standard authorization header:

```http
Authorization: Bearer replace-with-at-least-32-random-characters
```

Production requires authentication and refuses to start if it is disabled, no
key is configured, or any key is shorter than 32 characters. Multiple keys can
be comma-separated during client separation or key rotation. Keys are held as
secrets, hashed before comparison and limiter bucketing, compared in constant
time, and never added to logs or telemetry.

Authentication failures return `401`; exceeded request limits return `429`
with `Retry-After`; and exhausted workflow capacity returns `503` immediately
instead of building an unbounded queue. Rate and concurrency state is local to
each API process. With multiple `API_WORKERS`, the effective service-wide limits
are multiplied by the worker count. Use a shared gateway or Redis-backed limiter
when limits must be enforced globally across workers or application instances.

Start the development server on localhost:

```powershell
data-agent-api
```

The equivalent source-checkout command is
`uvicorn data_agent.api:app --host 127.0.0.1 --port 8000`.

Interactive OpenAPI documentation is available at
`http://127.0.0.1:8000/docs`. Check liveness with:

```http
GET /health
```

`GET /health/live` is the explicit liveness endpoint. `GET /health/ready`
reports whether startup completed and the process is accepting work. Enable
`API_READINESS_DATABASE_ENABLED=true` to require a successful bounded
PostgreSQL `SELECT 1` before readiness succeeds. Database failure details are
never returned to callers.

Submit a question with:

```http
POST /api/v1/query
Content-Type: application/json

{
  "question": "What payment methods are available in the database?"
}
```

The response contains only the public workflow contract:

```json
{
  "run_id": "correlation-id",
  "status": "success",
  "route": "sql",
  "final_answer": "The available payment methods are ...",
  "workflow_error": ""
}
```

The API also returns the correlation ID in the `X-Request-ID` response header.
Invalid models return HTTP 422, oversized bodies return HTTP 413, and workflow
errors return HTTP 500 with safe details. Request bodies default to a 16 KiB
limit controlled by `API_MAX_REQUEST_BYTES`.

### Production container

Build the multi-stage image from the repository root:

```powershell
docker build --tag data-agent:local .
```

Create a production environment file containing runtime secrets and settings,
then start the non-root container:

```powershell
docker run --rm --name data-agent `
  --publish 8015:8015 `
  --env-file .env.production `
  data-agent:local
```

At minimum, production requires `API_KEYS` and the selected LLM provider key.
Provide `DATABASE_URL` when SQL requests or database readiness are enabled.
Secrets are supplied at runtime and `.dockerignore` prevents local `.env` files
from entering the build context.

The image runs as UID/GID `10001`, installs frozen production dependencies in a
builder stage, and contains no development dependency set. It includes Alembic
and the baseline CSV files so migrations can be run using the same image:

```powershell
docker run --rm --env-file .env.production data-agent:local alembic upgrade head
```

Docker probes `/health/live`; orchestration platforms should use
`/health/ready` for traffic admission. During shutdown the application becomes
unready, waits up to `API_GRACEFUL_SHUTDOWN_SECONDS` for active workflows, and
then flushes telemetry. Relevant settings are:

```dotenv
API_GRACEFUL_SHUTDOWN_SECONDS=30
API_READINESS_DATABASE_ENABLED=true
API_READINESS_TIMEOUT_SECONDS=3
```

The writable `/app/data/extract` and `/app/data/transform` directories belong
to the non-root runtime user. Mount those directories separately when ETL
outputs must survive container replacement so the packaged seed data remains
available.

### Compose stack

The included Compose stack starts PostgreSQL, runs migrations once, starts an
OpenTelemetry Collector, and admits API traffic only after the database is
healthy and migrations succeed. Create the local runtime settings first:

```powershell
Copy-Item .env.compose.example .env.compose
```

Replace `POSTGRES_PASSWORD` and `API_KEYS` in `.env.compose`, add the API key
for the selected LLM provider, and start the stack:

```powershell
docker compose --env-file .env.compose up --build --detach
docker compose ps
```

With the supplied Compose settings, the API is available at
`http://localhost:8015` and PostgreSQL at `localhost:5445`. Send the value from
`API_KEYS` as a bearer token. The API and migration containers continue to use
PostgreSQL port `5432` inside the Compose network. The collector is reachable
only inside that network; inspect locally exported telemetry with:

```powershell
docker compose logs --follow otel-collector
```

Interactive API documentation is enabled for this local stack at
`http://localhost:8015/docs`. Disable it for an externally exposed deployment
by setting `API_DOCS_ENABLED=false`.

Stop containers without deleting database or ETL data using
`docker compose down`. Running `docker compose down --volumes` also deletes all
three named data volumes and should only be used when a full reset is intended.

Compose forces production-safe internal values for `APP_ENVIRONMENT`,
`API_HOST`, `API_PORT`, database readiness, `DATABASE_URL`, and the two OTLP
endpoints. Compose-only variables are `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_HOST_PORT`, `API_HOST_PORT`,
`API_STOP_GRACE_PERIOD`, `DATA_AGENT_TAG`, and `COMPOSE_ENV_FILE`; they configure
orchestration and are not application settings. `POSTGRES_HOST_PORT` and
`API_HOST_PORT` change host ports while the containers continue listening on
ports `5432` and `8000`, respectively.

### Python

Submit one request through the installed CLI:

```powershell
data-agent "What payment methods are available in the database?"
```

The command prints the public final answer and exits with code 1 when the
workflow returns `error`. The equivalent source-checkout command is
`python -m data_agent.cli "your question"`.

Or invoke the router directly:

```python
from langchain_core.messages import HumanMessage
from data_agent.agents.data_analyst import data_analyst

result = data_analyst.invoke(
    {"messages": [HumanMessage(content="What payment methods are available in the database?")]}
)
print(result)
```

Example requests:

- SQL: “What is the total amount of completed credit-card payments during April
  2026, based on `payment_time`?”
- Extraction: “Extract records from this HTTPS JSON endpoint into
  `data/extract` as CSV.”
- Transformation: “Filter `data/extract/extracted_data.csv` to these values
  and save the result in `data/transform` as CSV.”

## Workflows

Every compiled workflow exposes the same caller-facing output fields:

| Field | Meaning |
| --- | --- |
| `run_id` | Correlation ID shared by the router and selected child workflow |
| `status` | `pending`, `success`, `needs_clarification`, `rejected`, or `error` |
| `final_answer` | User-facing answer, clarification, rejection, or safe error message |
| `workflow_error` | Machine-readable safe diagnostic when `status` is `error` |
| `messages` | Conversation snapshot containing LangChain messages |

The main router normalizes child-workflow results to this contract. It adds only
the child workflow's final answer to its messages rather than embedding the
child's entire state dictionary. SQL-specific diagnostic fields remain
available when invoking the SQL analyst directly.

### Router

The main graph sends the latest message to a structured-output model. A response
of `sql` enters the SQL analyst; `etl` enters the ETL analyst. Other values
are rejected.

### SQL analyst

The SQL workflow:

1. Preserves the original question without LLM rewriting.
2. Loads schema metadata without sample rows, plus approved categorical values.
3. Classifies the question as `clear`, `ambiguous`, `unsupported`, or
   `error`.
4. Generates PostgreSQL only for a clear question.
5. Applies deterministic safety validation.
6. Uses an LLM judge to check relevance and categorical literals.
7. Revalidates and runs approved SQL in a read-only transaction.
8. Summarizes the result.

Only one `SELECT`, optionally using `WITH`, is permitted. Validation blocks
writes and administrative operations, `SELECT INTO`, row locks, multiple
statements, and unsafe PostgreSQL functions. Empty results return a direct
no-matches response, and handled failures stop without inventing an answer.

Clarification is single-turn: submit a new question containing the original
request and clarified metric, timestamp, status, or filter. There is no
persistent clarification session. The LLM judge is a guardrail, not a guarantee
of semantic correctness.

### ETL analyst

The ETL graph lets the model choose extraction or transformation, executes the
bounded tool, returns its result, and asks the model for the final response.

## Data model

- `users`: riders and drivers.
- `vehicles`: vehicles belonging to drivers.
- `rides`: trips, participants, timestamps, locations, fare, and status.
- `payments`: payments linked to rides and users.
- `ratings`: ratings linked to rides, riders, and drivers.

ORM relationships cover rider and driver roles, payments, ratings, and driver
vehicles. Alembic creates the tables and loads the supplied CSV seed data.

## Project structure

```text
data_agent/
├── docs/                    # Product, architecture, design, and database documents
├── docker/
│   └── otel-collector.yaml # Local OTLP collector pipeline
├── data/
│   ├── extract/            # API extraction output
│   └── transform/          # Transformation output
├── migrations/             # Alembic environment and revisions
├── src/
│   └── data_agent/
│       ├── agents/         # Router, SQL, and ETL graphs
│       ├── agentschemas/   # Workflow state and structured LLM schemas
│       ├── models/         # SQLAlchemy ORM models
│       ├── schemas/        # Pydantic domain schemas
│       ├── utils/          # Database, safety, LLM, and ETL utilities
│       ├── api.py          # Versioned FastAPI interface
│       ├── cli.py          # One-shot command-line interface
│       └── config.py       # Validated settings
├── tests/                  # Automated offline tests
├── .env.compose.example    # Compose runtime settings template
├── .env.example            # Configuration template
├── compose.yaml            # Production-style local service stack
├── Dockerfile              # Multi-stage non-root application image
├── MANIFEST.in             # Source-distribution asset manifest
├── alembic.ini             # Alembic configuration
├── pyproject.toml          # Project and test configuration
├── requirements.txt        # Pinned pip dependencies
└── uv.lock                 # Reproducible uv lock
```

## Database migrations

Use Alembic as the only mechanism for creating or changing production tables;
do not call `Base.metadata.create_all()` in application startup code. Before an
upgrade, back up any database whose data cannot be recreated and test the same
migration against a staging copy.

```powershell
alembic upgrade head
alembic current
alembic history
alembic revision --autogenerate -m "Describe the change"
alembic check
alembic downgrade -1
```

Review every autogenerated revision before applying it. In particular, verify
table and column renames, destructive operations, server defaults, indexes, and
foreign keys. Commit the model change and its migration in the same change set.

The migration history currently consists of a schema baseline followed by the
CSV seed-data revision. Seed files are resolved from the repository `data/`
directory, so seed migrations may be launched from any working directory within
a source checkout.

CI provisions an empty PostgreSQL database and verifies that migrations upgrade
to `head`, match the ORM metadata, load the baseline data, and downgrade to
`base`. To run this lifecycle test locally, point the dedicated variable at a
disposable PostgreSQL database whose name contains `test`:

```powershell
$env:MIGRATION_TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/data_agent_test"
pytest tests/test_migrations.py
```

The lifecycle test drops application tables during its downgrade check. Never
set `MIGRATION_TEST_DATABASE_URL` to a development, staging, or production
database.

## Tests

Run the offline suite from the repository root:

```powershell
python -m pytest -q
```

Tests isolate machine-specific `.env` values and mock model, database, and
network boundaries where appropriate. They do not require a live API, live
database, or real provider key.

## Quality controls

Run the same local gates enforced by GitHub Actions:

```powershell
ruff check .
ruff format --check .
python -m pytest --cov --cov-report=term-missing
```

Ruff enforces syntax, import ordering, undefined-name, and formatting rules for
Python 3.13. Coverage measures branches as well as statements and requires at
least 85% across the application modules. Direct-execution demonstration blocks
are excluded from coverage.

The `.github/workflows/quality.yml` workflow installs the locked environment,
runs all three Python gates, builds distributions, validates `compose.yaml`,
and builds the production image for every push and pull request. The job has
read-only repository permissions and a 15-minute timeout.

## Graph images

Run an agent module to regenerate its Mermaid PNG:

```powershell
python -m data_agent.agents.data_analyst
python -m data_agent.agents.sql_analyst
python -m data_agent.agents.etl_analyst
```

Outputs are `data_agent_graph.png`, `sql_analyst_graph.png`, and
`etl_analyst_graph.png`.
