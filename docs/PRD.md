# Product requirements document

## 1. Product summary

Data Agent is a natural-language analytics service. It classifies a request as
either a PostgreSQL analysis task or an ETL task, runs the selected bounded
workflow, and returns a consistent result contract through an HTTP API or CLI.

The product is currently an alpha application intended for controlled internal
use. It is not a general-purpose code execution agent or an unrestricted SQL
client.

## 2. Problem statement

People who need answers from structured data often lack the SQL or data
engineering expertise required to retrieve and reshape it safely. Direct use of
an LLM introduces material risks: invented schema, incorrect categorical
literals, destructive SQL, unrestricted network requests, arbitrary generated
code, and unbounded file access.

Data Agent reduces those risks by combining LLM interpretation with explicit
schemas, deterministic validation, bounded execution, authentication, and
operational telemetry.

## 3. Goals

- Let authenticated users ask natural-language questions about a known
  PostgreSQL database.
- Clarify materially ambiguous questions before executing SQL.
- Ground categorical filters in actual approved database values.
- Execute only one read-only PostgreSQL query within a timeout.
- Extract bounded records from HTTPS JSON APIs and save supported data formats.
- Apply validated declarative dataframe transformations without executing
  generated code.
- Return a stable, safe response contract for success and failure.
- Support OpenAI and Anthropic today while allowing provider adapters later.
- Run reproducibly through Python or a production-style Docker Compose stack.
- Emit useful logs, traces, and bounded metrics without sensitive payloads.

## 4. Non-goals

- Database writes, schema administration, or autonomous data correction.
- Arbitrary Python, SQL, shell, or expression execution in ETL transformations.
- General web crawling, browser automation, or non-JSON extraction.
- A persistent multi-turn clarification session.
- A business-intelligence dashboard or report designer.
- Cross-instance distributed rate limiting.
- High availability, multi-region deployment, or vendor-specific telemetry
  storage in the current release.

## 5. Users and use cases

### Primary users

- Data consumers who need answers from ride-sharing operational data.
- Analysts who want bounded extraction or transformation without writing code.
- Operators who deploy, secure, monitor, and troubleshoot the service.
- Developers who extend providers, workflows, models, and tests.

### Representative use cases

1. Sum payment amounts by payment method for a defined month.
2. Count completed rides using an explicitly selected ride timestamp.
3. Discover available values such as `credit_card` or a ride status and use the
   exact stored literal in SQL.
4. Extract records from an HTTPS JSON endpoint into CSV, JSON Lines, or Parquet.
5. Filter, select, rename, deduplicate, sort, and limit a local dataset.

## 6. Functional requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-001 | The service shall accept a question of 1–4,000 characters through `POST /api/v1/query`. | Invalid input returns HTTP 422. |
| FR-002 | The router shall select only `sql` or `etl`. | Structured router output and routing tests. |
| FR-003 | Every workflow shall return `run_id`, `status`, `final_answer`, and `workflow_error`; the API shall also return `route`. | Response-model and workflow tests. |
| FR-004 | The SQL workflow shall discover tables and columns only from the configured schema. | Schema discovery filters by schema and table. |
| FR-005 | The SQL workflow shall include only configured low-cardinality values in LLM metadata. | `SQL_CATEGORICAL_COLUMNS` allowlist and value cap. |
| FR-006 | The SQL workflow shall reject ambiguous or unsupported questions before SQL generation. | `needs_clarification` or `rejected` terminal state. |
| FR-007 | SQL execution shall allow one `SELECT` or `WITH` statement and reject writes, administrative operations, `SELECT INTO`, row locks, multiple statements, and denied functions. | Deterministic validation before and immediately before execution. |
| FR-008 | Approved SQL shall execute in a database read-only transaction with a configurable timeout. | Database utility and integration tests. |
| FR-009 | Empty SQL results shall return a deterministic no-matches response. | SQL workflow tests. |
| FR-010 | Extraction shall accept HTTPS URLs without embedded credentials and reject redirects, cross-origin pagination, and pagination cycles. | Extractor validation and tests. |
| FR-011 | Extraction shall enforce configured retry, page, row, and timeout bounds. | Extractor settings and tests. |
| FR-012 | ETL output shall be limited to `data/extract` or `data/transform`, and existing output files shall not be overwritten. | Canonical path checks and ETL tests. |
| FR-013 | Transformations shall use a validated declarative plan and support only approved operations. | `TransformationPlan` schema and ETL tests. |
| FR-014 | Production API requests shall require a configured bearer key of at least 32 characters. | Startup validation and HTTP 401 tests. |
| FR-015 | The API shall enforce per-key sliding-window rate limits and a process-local concurrency limit. | HTTP 429/503 behavior and security tests. |
| FR-016 | The service shall expose liveness and readiness endpoints; database readiness shall be configurable. | `/health/live` and `/health/ready` tests. |
| FR-017 | Database changes shall be applied through Alembic before the API accepts traffic. | Compose migration startup gate and migration tests. |
| FR-018 | Operators shall be able to select an LLM provider and override low, medium, and high model IDs through configuration. | Provider adapter and configuration tests. |

## 7. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 Security | Secrets shall be supplied at runtime and shall not be logged, traced, included in images, or returned in errors. |
| NFR-002 Privacy | Custom telemetry shall exclude prompts, generated SQL, query results, records, credentials, full URLs, and file paths. |
| NFR-003 Reliability | External calls and SQL shall have finite timeouts; extraction retries shall be bounded. |
| NFR-004 Availability | Readiness shall remain false during startup and graceful shutdown and when the configured database check fails. |
| NFR-005 Operability | Requests and workflow nodes shall carry a correlation `run_id`; logs, traces, and metrics shall expose safe operational dimensions. |
| NFR-006 Portability | The package shall run on Python 3.13+ and in the supplied non-root Linux container. |
| NFR-007 Maintainability | CI shall enforce linting, formatting, branch coverage of at least 85%, packaging, Compose validation, and image build. |
| NFR-008 Performance safety | Request size, SQL time, extraction size, concurrency, and rate limits shall be configurable and bounded. |

## 8. User-visible contract

The primary response shape is:

```json
{
  "run_id": "correlation-id",
  "status": "success",
  "route": "sql",
  "final_answer": "User-facing result",
  "workflow_error": ""
}
```

Allowed workflow statuses are `pending`, `success`, `needs_clarification`,
`rejected`, and `error`. The API returns the correlation identifier in the
`X-Request-ID` header.

## 9. Success criteria

- Supported, unambiguous SQL questions return correct database-derived answers.
- Ambiguous questions do not execute SQL and request a specific clarification.
- Unsafe SQL and invalid ETL operations are blocked deterministically.
- The deployed API passes liveness and database-backed readiness checks.
- Operational failures can be correlated without exposing user or database data.
- The automated quality suite remains green with at least 85% branch coverage.

## 10. Risks and future work

- LLM classification and semantic review can be wrong; expand evaluation
  datasets and regression tests before broader use.
- In-memory rate limits multiply across workers and replicas; adopt a shared
  gateway or distributed limiter for horizontal scaling.
- The debug telemetry exporter is for local operation; production should route
  the collector to a durable observability backend such as LangSmith or an
  OpenTelemetry-compatible platform.
- Database permissions should independently enforce read-only access for the API
  role, even though the application opens read-only transactions.
- A persistent clarification protocol and richer policy/audit controls remain
  candidates for a later release.
