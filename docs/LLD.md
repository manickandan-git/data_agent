# Low-level design

## 1. Runtime entry points

| Entry point | Callable | Behavior |
| --- | --- | --- |
| `data-agent-api` | `data_agent.api:run` | Starts Uvicorn using validated API settings |
| `data-agent` | `data_agent.cli:run` | Runs one routed request and prints the final answer |
| ASGI import | `data_agent.api:app` | Prebuilt FastAPI application |
| Graph import | `data_agent.agents.data_analyst:data_analyst` | Compiled root LangGraph workflow |

Importing modules does not configure logging, contact external systems, or run
demonstration code.

## 2. Configuration implementation

`EnvironmentSelector` reads `APP_ENVIRONMENT` first. `Settings` then loads
`.env` followed by `.env.<environment>` from the source root and current working
directory; process environment variables have highest precedence. `get_config`
is cached.

Important cross-field rules:

- Reload requires exactly one worker and is forbidden in staging/production.
- Production rejects debug logging and disabled API authentication.
- Enabled telemetry requires a trace endpoint.
- Enabled authentication requires one or more comma-separated keys, each at
  least 32 characters.
- Database-backed readiness requires a database URL.

Callers that modify settings in-process must clear `get_config` and LLM client
caches or restart the process.

## 3. HTTP request processing

`create_app` supports dependency injection of the workflow, settings, telemetry
exporters/readers, and readiness check for offline tests.

Request sequence for `POST /api/v1/query`:

1. Middleware rejects invalid or oversized `Content-Length` and bodies above
   `API_MAX_REQUEST_BYTES` with HTTP 413.
2. Pydantic validates `QueryRequest`; invalid payloads return HTTP 422.
3. `HTTPBearer` extracts credentials.
4. `APIKeyAuthenticator` hashes the supplied key and constant-time compares it
   with precomputed configured-key digests. Failure returns HTTP 401 and
   `WWW-Authenticate: Bearer`.
5. `SlidingWindowRateLimiter.allow` prunes expired timestamps and either records
   the request or returns HTTP 429 with `Retry-After`.
6. `ConcurrencyLimiter.try_acquire` rejects excess active workflows with HTTP
   503; acquisition is always released in `finally`.
7. The synchronous LangGraph invocation runs in FastAPI's thread pool.
8. The graph result maps to `QueryResponse`; workflow error status maps to HTTP
   500, and `X-Request-ID` carries the run ID.

Health endpoints bypass authentication and workflow limits. Readiness checks
the lifecycle accepting flag and, when enabled, performs a bounded PostgreSQL
`SELECT 1`.

## 4. Workflow state contracts

### Common output

`WorkflowOutput` defines:

- `run_id: str`
- `status: pending | success | needs_clarification | rejected | error`
- `final_answer: str`
- `workflow_error: str`

### Router state

`DataSchema` adds `messages` and `route_response`. `RouterSchema` constrains the
model result to `sql` or `etl`.

### SQL state

`AgentSchema` adds the original/curated question, schema context, question
review status and feedback, prompt context, generated SQL, safety result and
comments, execution result, and messages.

Key transitions:

| Node | Success transition | Failure/alternate transition |
| --- | --- | --- |
| `curate_question` | `curate_prompt_query_context` | `finish_error` for empty input |
| `curate_prompt_query_context` | `validate_question` | `finish_error` when schema is unavailable |
| `validate_question` | `generate_sql_query` when clear | clarification/rejection terminal node, or error |
| `generate_sql_query` | `is_safe_sql` | `finish_error` |
| `is_safe_sql` | execute when approved | cancel when unsafe or irrelevant |
| `execute_sql_query` | `representation_final_answer` | `finish_error` |
| `representation_final_answer` | terminal success | `finish_error` |

The original question is stripped but not rewritten. Any model/configuration,
database, or response-shape exception is converted to a safe workflow error.

### ETL state

`ETLSchema` adds messages to the common output. The graph alternates between
`llm_node` and `tool_node` until the model returns no tool calls or a tool
returns an error prefix. Tool names are resolved only from the fixed registry.

## 5. SQL implementation

### Metadata discovery

`AsyncDatabaseUtil.schema_details`:

- fetches base tables from `information_schema.tables` for one schema;
- fetches columns for the exact schema/table pair;
- queries distinct values only for the configured table/column intersection;
- safely quotes dynamic identifiers;
- caps categorical values; and
- disables sample records in the SQL workflow.

### Deterministic validation

`validate_read_only_sql` first replaces comments, string literals, quoted
identifiers, and dollar-quoted blocks with whitespace, then tokenizes the
remaining structure. It rejects:

- empty input or a first token other than `SELECT`/`WITH`;
- multiple statements or a non-terminal semicolon;
- write, DDL, administrative, lock, notification, or session-setting keywords;
- `SELECT INTO`;
- `FOR UPDATE` and `FOR SHARE`; and
- denied functions such as file access, large-object import/export, sequence
  mutation, directory listing, and sleep functions.

Validation runs before the LLM judge and again immediately before execution.
`execute_read_only_sql` executes through asyncpg inside
`connection.transaction(readonly=True)` with the configured timeout.

In Compose, defense in depth is provided by separate PostgreSQL identities:

- `POSTGRES_USER` is the existing database administrator and is available only
  to the role-bootstrap service.
- `POSTGRES_MIGRATION_USER` owns the `public` schema and its tables/sequences and
  is used only by Alembic.
- `POSTGRES_APP_USER` receives `CONNECT`, schema `USAGE`, and `SELECT` on current
  and future tables/sequences. Its database-specific
  `default_transaction_read_only` setting is enabled.

The idempotent bootstrap script rejects duplicate role names, removes public
schema creation from `PUBLIC`, transfers existing objects to the migration
owner, and refreshes role passwords/grants on each Compose reconciliation.

## 6. ETL implementation

### Extraction algorithm

`fetch_records` validates the initial origin, disables environment proxies and
`.netrc`, and sends `Accept: application/json`. For each page it:

1. Requires the same HTTPS origin and rejects embedded credentials.
2. Detects previously visited URLs.
3. Retries only timeouts, connection failures, HTTP 429, and HTTP 5xx using
   capped exponential backoff.
4. Rejects redirects and other HTTP errors without returning body or URL data.
5. Resolves the configured dotted records path and requires a list of objects.
6. Enforces total row and page limits.
7. Resolves the next-page path or finishes.

Bearer credentials are attached only if `ETL_AUTH_ORIGIN` exactly equals the
request origin.

### Filesystem containment

`ETLTools._resolve_allowed_path` resolves canonical absolute paths and uses
`Path.is_relative_to` to enforce the intended root. Extraction can write only
under `data/extract`; transformation can read under `data` and write under
`data/transform`. `_ensure_new_output` prevents replacement of existing files.

### Transformation plan

`TransformationPlan` allows at most 20 filters and 10 sort rules. Supported
filters are `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `in`, `not_in`, `contains`,
`starts_with`, `ends_with`, `is_null`, and `not_null`. Operations run in this
fixed order:

1. filters;
2. column selection;
3. column renaming;
4. duplicate removal;
5. sorting; and
6. row limit.

Every referenced column must exist, renamed columns must be unique, and the
optional row limit is between 1 and 100,000.

## 7. LLM layer

`pick_llm(difficulty)` selects a cached provider client for `low`, `medium`, or
`high`. `structured_llm` adds a Pydantic output schema. Built-in adapters
encapsulate OpenAI- and Anthropic-specific construction; additional providers
register through `register_provider`.

`observed_llm_invoke` records operation duration, outcome, provider, model,
difficulty, and available usage counts. It does not record prompt or response
content.

## 8. Observability implementation

- `configure_observability` installs JSON or console logging explicitly.
- `observed_node` wraps graph nodes and emits start/completion/failure events.
- `observed_operation` and `observed_async_operation` wrap important utility
  operations.
- `configure_telemetry` configures tracing, metrics, FastAPI instrumentation,
  resource attributes, sampling, and OTLP HTTP export.
- `record_value` emits bounded token, row, page, and retry measurements.

Custom labels are low-cardinality operational values. Raw prompts, SQL, URLs,
paths, query output, and records are excluded.

## 9. Error and status mapping

| Condition | HTTP/workflow result |
| --- | --- |
| Missing/invalid bearer key | HTTP 401 |
| Rate limit exceeded | HTTP 429 with `Retry-After` |
| Concurrency exhausted | HTTP 503 with `Retry-After` |
| Oversized request | HTTP 413 |
| Invalid request schema | HTTP 422 |
| Ambiguous question | HTTP 200, `needs_clarification` |
| Unsupported question or rejected SQL | HTTP 200, `rejected` |
| Handled workflow failure | HTTP 500, `error` with safe diagnostic |
| Successful workflow | HTTP 200, `success` |

## 10. Extension rules

- Add a provider through an adapter rather than branching inside workflows.
- Add graph state only through Pydantic contracts and update all terminal output
  mappings.
- Add a categorical field only after confirming it is non-sensitive and
  low-cardinality.
- Add a transformation only as a validated declarative operation with focused
  tests; never accept generated executable code.
- Add or change relational fields through an ORM change and reviewed Alembic
  migration in the same change set.
