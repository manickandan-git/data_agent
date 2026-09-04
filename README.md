# Data Agent

An intelligent multi-agent system built with LangGraph that automatically routes data requests to specialized agents. The system intelligently determines whether queries require SQL data extraction or ETL operations.

## Features

- **Intelligent Routing**: Automatically routes queries to SQL or ETL agents based on request type
- **Multi-Agent Architecture**: Specialized agents for different data operations
  - **SQL Analyst**: Handles database queries and structured data extraction
  - **ETL Analyst**: Handles API data extraction, transformation, and loading
- **LangGraph Integration**: Robust workflow orchestration with conditional routing
- **LLM-Powered Router**: Uses language models to intelligently classify requests

## Project Structure

```
data_agent/
├── __init__.py                # Package initialization
├── config.py                  # Configuration settings
├── main.py                    # Application entry point
├── README.md                  # This file
│
├── agents/                    # Specialized agent implementations
│   ├── __init__.py
│   ├── data_analyst.py       # Main orchestrator with routing logic
│   ├── etl_analyst.py        # ETL operations (extract, transform, load)
│   └── sql_analyst.py        # SQL queries and database operations
│
├── agentschemas/             # Pydantic schemas for data validation
│   ├── __init__.py
│   ├── agent.py              # Agent-specific schemas
│   ├── data.py               # DataSchema with messages and routing
│   ├── etl.py                # ETL operation schemas
│   ├── judge.py              # Judgment/validation schemas
│   └── router.py             # RouterSchema for LLM routing decisions
│
├── models/                   # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── base.py               # Base model configuration
│   ├── user.py               # User model
│   ├── vehicle.py            # Vehicle model
│   ├── ride.py               # Ride model
│   ├── payment.py            # Payment model
│   └── rating.py             # Rating model
│
├── schemas/                  # Pydantic request/response schemas
│   ├── __init__.py
│   ├── user.py               # User schemas
│   ├── vehicle.py            # Vehicle schemas
│   ├── ride.py               # Ride schemas
│   ├── payment.py            # Payment schemas
│   └── rating.py             # Rating schemas
│
├── utils/                    # Utility modules
│   ├── __init__.py
│   ├── llm_pick.py          # LLM selection and initialization
│   ├── database.py          # Database connection and utilities
│   └── etl_tools.py         # ETL utility functions
│
├── data/                     # Data storage directory
│   └── extract/              # Extracted data storage
│
└── migrations/               # Database migration files (Alembic)
    ├── env.py               # Migration environment setup
    ├── script.py.mako       # Migration template for new migrations
    ├── README               # Alembic README
    └── versions/            # Database migration versions
        ├── a86b191887cf_insert_csv_data_for_all_tables.py
        └── c8e2638fcf8a_create_ride_sharing_tables.py
```

## Installation

### Option 1: Using UV (Recommended - Faster)

[UV](https://docs.astral.sh/uv/) is a fast Python package installer written in Rust.

1. Clone the repository:
```bash
git clone <repository-url>
cd data_agent
```

2. Install UV (if not already installed):
```bash
# On Windows
curl -LsSf https://astral.sh/uv/install.ps1 | powershell -c -

# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Option 2: Using pip

1. Clone the repository:
```bash
git clone <repository-url>
cd data_agent
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Configuration and LLM providers

Copy `.env.example` to `.env` and supply only the selected provider's key.
Configuration is loaded relative to the repository, independent of the working
directory. Secrets are redacted in settings representations. Clients are created
when workflows run, not when modules are imported.

`LLM_PROVIDER=openai` uses `gpt-5.6-luna` for low,
`gpt-5.6-terra` for medium, and `gpt-5.6-sol` for high. Override each with
`LLM_MODEL_LOW`, `LLM_MODEL_MEDIUM`, and `LLM_MODEL_HIGH`.

To use Anthropic, set `LLM_PROVIDER=anthropic`, supply `ANTHROPIC_API_KEY`, and
set the three model settings to Anthropic model IDs available to your account.
OpenAI credentials are not required for Anthropic. Selected models must support
tool calling and structured outputs. No live provider calls are made by the tests.

`LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, and `LLM_MAX_TOKENS`
control model requests. `OPENAI_BASE_URL` optionally selects an OpenAI-compatible
endpoint; use only a trusted endpoint, since it receives your key and prompts.
Compatibility with third-party endpoints must be verified separately.

`DATABASE_URL` is required only for database operations. `DATABASE_SCHEMA`,
`SQL_ROW_LIMIT`, and `SQL_TIMEOUT_SECONDS` configure schema discovery, the prompted
default row limit, and query timeout. The row limit is a generation instruction,
not a database-enforced result cap. Migrations also read these settings; changing
`DATABASE_SCHEMA` does not relocate the existing `public` ORM tables/migrations.

Additional providers can register a `ProviderAdapter` with `register_provider`
in `utils/llm_pick.py` before invoking a graph. The adapter builds a LangChain
chat model and specifies any provider-specific structured-output method.
Agent workflows do not need provider-specific edits. Settings are cached for the
process; restart after editing `.env` or call `reset_llm_clients()` from
`utils.llm_pick` to clear both settings and model clients.

The default GPT-5.6 family uses the Responses API with explicit
`OPENAI_REASONING_EFFORT=low` and omits temperature. Legacy/custom model overrides
retain Chat Completions and temperature. Output is kept in LangChain's `v0`
message format to preserve existing agent text/tool contracts. Model clients are
reused by the default `LLMFactory`; tests can inject their own settings/factory.
No automatic failover changes providers, endpoints, or model costs.
Private `.env` model overrides take priority; clear them to adopt the new defaults.
See [OpenAI migration guidance](https://developers.openai.com/api/docs/guides/latest-model).

### Basic Example

API extraction supports HTTPS endpoints with bounded timeouts, retries for
connection/timeouts, HTTP 429 and 5xx, and same-origin next-link pagination.
Configure limits using the `ETL_*` settings in `.env.example`. If a limit is
exceeded, extraction fails instead of saving an incomplete dataset.
`records_path` defaults to `results`; use a dotted path such as `data.items`, or
an empty string for a root JSON array. Records must be objects. `next_path`
defaults to `next`; an absent top-level `next` ends pagination. Use an empty
string to disable pagination, or a dotted path such as `links.next`.
Numeric offsets/cursors and authentication schemes other than bearer tokens
are not implemented. Redirects and cross-origin pagination are rejected.

For authentication, set `ETL_BEARER_TOKEN` and a matching `ETL_AUTH_ORIGIN`
(for example, `https://api.example.com`). Tokens are never tool arguments.
Environment proxy and `.netrc` inheritance are disabled. Error messages omit
response bodies and request URLs. Outputs remain confined to `data/extract`
and existing outputs are not overwritten. This is not a network sandbox:
deployments must enforce egress rules if untrusted users can supply URLs.
Page/row limits do not impose a byte-size or total elapsed-time limit.

```python
from langchain_core.messages import HumanMessage
from agents.data_analyst import data_analyst

response = data_analyst.invoke({
    "messages": [HumanMessage(content="Extract data from the Pokemon API and save to CSV")]
})

print(response)
```

### Routing Examples

The system automatically routes based on query type:

- **ETL Route**: "Extract data from API endpoint..."
- **SQL Route**: "Query the database for...", "Get sales data where..."

## Architecture

### SQL workflow

The SQL branch preserves the original question, loads schema metadata without
sample records, validates question answerability and ambiguity, generates SQL once,
runs deterministic safety validation and
an LLM relevance review, executes in a read-only transaction, then summarizes.
It requires approval again at execution time. Empty results receive a direct
no-matches answer; schema, generation, and execution failures terminate without
inventing a summary. `workflow_error` identifies handled failures and
`final_answer` is populated for success, rejection, and handled errors.
The SQL state's message list is a snapshot rather than an accumulating reducer,
so returning full state no longer duplicates the conversation at every node.
Schema discovery still inspects all tables in the configured schema; automatic
relevant-table selection and async-native graph nodes are not implemented yet.

Question review returns `question_status` (`clear`, `ambiguous`, `unsupported`,
or `error`) and `question_feedback`. Only clear questions reach SQL generation.
Ambiguous questions return a specific clarification question in `final_answer`;
unsupported requests explain missing data. Validation failures stop execution.
The LLM review is a guardrail, not a guarantee of semantic correctness.
This is a single-turn workflow: after clarification, submit the original request
together with the clarified metric/filters as a new `user_question`. There is no
automatic persistent clarification session yet.

### Data Flow

```
User Query
    ↓
[START] → router_node (LLM decides route)
    ↓
    ├─→ [sql_node] → SQL Analyst → Database
    │
    └─→ [etl_node] → ETL Analyst → API/External Source
    ↓
Response
```

### Key Components

**router_node**: Uses LLM with RouterSchema to classify incoming requests as "sql" or "etl"

**sql_node**: Executes SQL queries with:
- Query generation and validation
- Safety checks
- Execution against database

**etl_node**: Handles data extraction with:
- API connectivity
- Data transformation
- File saving operations

## Schemas

### Agent Schemas (`agentschemas/`)
Pydantic models used for LLM orchestration and validation:

- **DataSchema**: Main workflow state with messages and routing decisions
- **RouterSchema**: LLM output for routing decisions ("sql" or "etl")
- **ETLSchema**: ETL operation parameters and results
- **AgentSchema**: Agent configuration and metadata
- **JudgeSchema**: Validation and quality checking

### Data Models (`models/`)
SQLAlchemy ORM models representing core business entities:

- **User**: User profiles and authentication
- **Vehicle**: Vehicle information and metadata
- **Ride**: Ride bookings and history
- **Payment**: Payment transactions
- **Rating**: Ride ratings and reviews

### API Schemas (`schemas/`)
Pydantic request/response schemas for API endpoints:

- **User Schemas**: Create, read, update operations
- **Vehicle Schemas**: Vehicle management
- **Ride Schemas**: Ride booking and tracking
- **Payment Schemas**: Payment processing
- **Rating Schemas**: Rating submissions

## Schemas

### DataSchema
Main state schema for the workflow:
- `messages`: List of conversation messages
- `route_response`: Routing decision ("sql" or "etl")

### RouterSchema
LLM output schema for routing decisions:
- `answer`: The routing decision

## Development

### Quick Reference - UV Commands

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate      # Windows

# Install dependencies
uv pip install -r requirements.txt

# Add a new package
uv pip install <package-name>

# Update dependencies
uv pip install --upgrade -r requirements.txt

# Freeze current dependencies
uv pip freeze > requirements.txt
```

### Running Tests
```bash
pytest tests/
```

### Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations.

**View migration status:**
```bash
alembic current
```

**Run all pending migrations:**
```bash
alembic upgrade head
```

**Create a new migration:**
```bash
alembic revision --autogenerate -m "Description of changes"
```

**Rollback to previous migration:**
```bash
alembic downgrade -1
```

**View migration history:**
```bash
alembic history
```

### Visualizing the Graph
The system generates a graph visualization:
```bash
python agents/data_analyst.py
# Generates: data_agent_graph.png
```

## Recent Changes

- Fixed Pydantic validation error in DataSchema by making `route_response` field optional with default value
- Improved agent integration and error handling

## Dependencies

- **langchain**: LLM framework
- **langgraph**: Graph-based workflow orchestration
- **pydantic**: Data validation
- Python 3.10+

## Contributing

1. Create a feature branch
2. Make changes and test thoroughly
3. Submit a pull request

## License

[Add license information here]

## Contact

For questions or issues, please open an issue in the repository.
