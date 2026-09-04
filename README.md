# Data Agent

Data Agent is a LangGraph application that routes natural-language requests to
an SQL analyst for PostgreSQL questions or an ETL analyst for JSON API
extraction and local dataset transformation.

It uses LangChain-compatible chat models, Pydantic structured outputs,
SQLAlchemy models, Alembic migrations, and pandas-based ETL operations.

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

## Installation

With `uv`:

```powershell
uv sync --dev
.venv\Scripts\Activate.ps1
```

Alternatively, use the pinned pip requirements:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`pyproject.toml` and `uv.lock` are the primary project and lock files.
`requirements.txt` provides a pinned pip-compatible environment.

## Configuration

Copy `.env.example` to `.env`. Configuration is loaded from the repository
directory regardless of the current working directory. Never commit real API
keys, database credentials, or bearer tokens.

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
`utils/llm_pick.py`; the workflows do not require provider-specific edits.

Request controls include `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`,
`LLM_MAX_RETRIES`, `LLM_MAX_TOKENS`, and `OPENAI_REASONING_EFFORT`.
The default GPT-5.6 models use the Responses API and reasoning effort without
temperature. Legacy or custom OpenAI overrides retain chat parameters.
`OPENAI_BASE_URL` must point only to a trusted compatible endpoint because it
receives the configured key and prompts.

Clients and settings are cached. Restart after editing `.env`, or call
`reset_llm_clients()` to clear both caches.

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

Run the example:

```powershell
python main.py
```

Or invoke the router directly:

```python
from langchain_core.messages import HumanMessage
from agents.data_analyst import data_analyst

result = data_analyst.invoke({
    "messages": [HumanMessage(
        content="What payment methods are available in the database?"
    )]
})
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
├── agents/                 # Router, SQL, and ETL graphs
├── agentschemas/           # Workflow state and structured LLM schemas
├── data/
│   ├── extract/            # API extraction output
│   └── transform/          # Transformation output
├── migrations/             # Alembic environment and revisions
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic domain schemas
├── tests/                  # Automated offline tests
├── utils/                  # Database, safety, LLM, and ETL utilities
├── .env.example            # Configuration template
├── alembic.ini             # Alembic configuration
├── config.py               # Validated application settings
├── main.py                 # Example entry point
├── pyproject.toml          # Project and test configuration
├── requirements.txt        # Pinned pip dependencies
└── uv.lock                 # Reproducible uv lock
```

## Database migrations

```powershell
alembic upgrade head
alembic current
alembic history
alembic revision --autogenerate -m "Describe the change"
alembic downgrade -1
```

## Tests

Run the offline suite from the repository root:

```powershell
python -m pytest -q
```

Tests isolate machine-specific `.env` values and mock model, database, and
network boundaries where appropriate. They do not require a live API, live
database, or real provider key.

## Graph images

Run an agent module to regenerate its Mermaid PNG:

```powershell
python -m agents.data_analyst
python -m agents.sql_analyst
python -m agents.etl_analyst
```

Outputs are `data_agent_graph.png`, `sql_analyst_graph.png`, and
`etl_analyst_graph.png`.
