# Production hardening roadmap

## 1. Purpose

This document records production improvements that are intentionally deferred.
They are not commitments in the current release and must be planned, reviewed,
implemented, and tested before the application is classified as suitable for
public or business-critical production use.

Each initiative should be delivered as a separate change set. Update the PRD,
architecture, HLD, LLD, runbooks, configuration templates, tests, and threat
model whenever an implementation changes their documented contracts.

## 2. Recommended sequence

| Order | Initiative | Priority | Depends on |
| --- | --- | --- | --- |
| 1 | Automated LLM evaluations | High | Representative evaluation dataset |
| 2 | Vulnerability scanning and dependency automation | High | CI permissions and remediation policy |
| 3 | Durable telemetry backend | High | Backend/vendor selection and retention policy |
| 4 | Secrets manager integration | High | Deployment platform selection |
| 5 | Database backup, restore, and production procedures | High | Target production database/platform |
| 6 | Shared rate limiting | Medium before horizontal scale; High before public exposure | Redis or gateway architecture decision |

The evaluation suite comes first because it establishes a measurable behavioral
baseline before infrastructure changes. Security scanning should begin early
because it can run continuously while the remaining platform choices are made.
The exact order of telemetry, secrets, and database operations may change once
the production hosting platform is selected. Shared rate limiting becomes a
release blocker when more than one API worker/replica is used or the service is
exposed publicly.

## 3. Shared rate limiting

### Objective

Replace process-local request counters with a limit shared across API workers,
containers, and hosts. Restarting or scaling the API must not reset or multiply
a client's effective allowance.

### Recommended approach

Use Redis-backed rate limiting first, while retaining the in-memory backend for
offline tests and single-process development. Add a production gateway later as
a complementary edge control for TLS termination, network filtering, and coarse
IP/client limits.

### Proposed configuration

```dotenv
API_RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://redis:6379/0
API_RATE_LIMIT_REDIS_PREFIX=data-agent:rate-limit
API_RATE_LIMIT_FAIL_OPEN=false
```

Raw API keys must never be used as Redis keys. Continue using a one-way digest
as the client identifier.

### Implementation tasks

- Define a `RateLimiter` protocol so HTTP code is backend-independent.
- Retain the current sliding-window limiter as the memory implementation.
- Implement an atomic Redis algorithm, preferably a Lua-backed sliding window
  or token bucket, with automatic key expiration.
- Validate Redis URLs and backend-specific configuration at startup.
- Add a private, health-checked Redis service and persistent volume to Compose.
- Decide connection-pool sizing and timeouts for each API worker.
- Fail closed in staging/production: return HTTP 503 if the shared limiter is
  unavailable. Development may optionally fall back to memory if explicitly
  configured.
- Emit safe metrics for allowed, rejected, and backend-error outcomes without
  client identifiers.
- Document Redis lifecycle, persistence, upgrades, and recovery.
- Consider gateway limits as an independent outer layer before public exposure.

### Verification and acceptance criteria

- Two API workers share one effective request allowance.
- Concurrent requests cannot exceed the configured allowance due to races.
- API/container restarts do not reset active Redis windows.
- Redis keys expire and contain only digested identifiers.
- Redis unavailability returns 503 in production and never bypasses limits.
- Unit, concurrency, integration, and Compose tests cover both backends.
- Load testing demonstrates acceptable limiter latency at the target throughput.

## 4. Durable telemetry backend

### Objective

Replace the collector's debug exporter with durable, searchable storage and
alerting for traces and metrics. Preserve the current payload-minimization rules.

### Decision required

Select an OpenTelemetry-compatible destination based on hosting platform,
budget, retention, access controls, and operational expertise. Candidates may
include a managed observability platform or a self-hosted stack. LangSmith may
be evaluated separately for LLM-specific traces and evaluations, subject to the
same data-governance review.

### Implementation tasks

- Define required dashboards, service-level indicators, alerts, and retention.
- Choose trace sampling rules for normal traffic and failures.
- Configure the collector exporter and authentication through runtime secrets.
- Add batching, retry, queue, memory limiting, and persistent queue/storage as
  supported by the selected collector distribution.
- Encrypt telemetry in transit and restrict backend access by role.
- Create dashboards for API traffic, latency, error rates, rate limiting, LLM
  calls, SQL execution, ETL operations, and readiness.
- Alert on sustained failures, latency, dropped telemetry, database readiness,
  and limiter/backend outages.
- Define collector failure behavior so telemetry loss does not take down normal
  application requests.
- Document incident investigation using `run_id`, `trace_id`, and `span_id`.

### Verification and acceptance criteria

- Traces and metrics survive application and collector restarts according to
  the selected durability design.
- Operators can find one request by `run_id` and follow its workflow spans.
- Alerts are tested with controlled failure scenarios.
- Retention and deletion behavior meet the approved policy.
- A privacy test confirms prompts, SQL text, query results, records, secrets,
  full URLs, and file paths are absent.

## 5. Secrets manager integration

### Objective

Remove production reliance on `.env` files and deliver credentials from a
managed secret store with auditable access and rotation.

### Decision required

Select the integration based on the deployment platform—for example, a cloud
secret manager, Vault, or orchestrator-native secret mechanism. Local
`.env.compose` remains acceptable only for development.

### Secrets in scope

- OpenAI and Anthropic API keys.
- Public API bearer keys.
- PostgreSQL administrator, migration, and application passwords.
- ETL bearer credentials.
- Redis credentials when shared rate limiting is implemented.
- Telemetry exporter credentials.

### Implementation tasks

- Inventory secrets, owners, consumers, rotation periods, and emergency
  revocation procedures.
- Give each service access only to the secrets it consumes; the API must not
  receive the PostgreSQL administrator or migration password.
- Inject secrets as mounted files or short-lived identity-based credentials
  where supported; avoid command-line arguments and image build arguments.
- Add configuration support for secret-file references if required.
- Redact secrets from logs, diagnostics, crash output, CI, and deployment plans.
- Configure workload identity and least-privilege secret-store policies.
- Implement overlapping-key rotation for API clients and provider keys.
- Add secret scanning for committed history and pull requests.
- Document development bootstrap separately from production delivery.

### Verification and acceptance criteria

- No production secret is stored in the repository, image, Compose file, CI
  output, or deployment manifest.
- Each workload can retrieve only its explicitly authorized secrets.
- Rotation succeeds without unplanned downtime.
- Revoked credentials stop working within the defined window.
- Startup fails safely when a required secret is missing or malformed.

## 6. Automated LLM evaluations

### Objective

Measure routing, ambiguity detection, SQL semantic correctness, categorical
grounding, refusal behavior, and answer quality independently of conventional
unit tests.

### Evaluation dataset

Build a versioned dataset containing:

- clear SQL questions with expected intent and approved SQL/result properties;
- ambiguous questions with expected clarification topics;
- unsupported and malicious questions with expected rejection;
- exact categorical mappings such as `credit card` → `credit_card`;
- timestamp ambiguities across request, pickup, drop-off, payment, and rating
  times;
- joins, aggregates, grouping, nulls, empty results, and boundary dates;
- ETL routing and tool-selection examples; and
- prompt-injection and SQL-safety adversarial cases.

Use synthetic or approved non-sensitive data. Do not send production records to
an evaluation provider without explicit governance approval.

### Implementation tasks

- Define deterministic graders for route, status, required filters, tables,
  joins, date bounds, grouping, read-only safety, and result equivalence.
- Use SQL parsing or execution against a disposable seeded database rather than
  exact SQL-string matching.
- Add model-based graders only where deterministic grading is insufficient.
- Record model/provider/version, prompt version, latency, token usage, and cost.
- Establish a checked-in baseline and allowable regression thresholds.
- Run a small deterministic set on pull requests and a broader scheduled suite
  with controlled budget.
- Separate flaky provider/network failures from behavioral failures.
- Require review when prompts, schemas, model defaults, or categorical metadata
  change.

### Verification and acceptance criteria

- The suite reports routing accuracy, clarification precision/recall, unsafe-SQL
  escape rate, execution/result accuracy, and categorical grounding accuracy.
- No unsafe SQL in the evaluation corpus reaches execution.
- Critical cases have a zero-regression policy.
- Results are reproducible enough to compare a candidate against the baseline.
- CI and scheduled runs publish a concise report without exposing prompts that
  contain sensitive information.

## 7. Backup, restore, and production procedures

### Objective

Prove that database data and required configuration can be recovered within
approved recovery objectives, and provide repeatable deployment/runbook steps.

### Decisions required

- Production PostgreSQL hosting model.
- Recovery point objective (RPO) and recovery time objective (RTO).
- Backup frequency, retention, encryption, geographic redundancy, and legal
  retention requirements.
- Deployment strategy: rolling, blue/green, or another controlled method.

### Implementation tasks

- Enable automated encrypted backups and, where required, point-in-time recovery.
- Separate database backup from ETL object/file retention policy.
- Create a restore runbook for a clean isolated environment.
- Schedule automated restore drills and verify row counts, constraints,
  migrations, application readiness, and representative queries.
- Document pre-deployment checks, migration review, backup confirmation,
  deployment, smoke tests, rollback, and incident escalation.
- Define backward-compatible migration rules and explicit handling for
  destructive migrations.
- Validate graceful shutdown and in-flight request behavior during deployment.
- Document ownership for deployment approval and database recovery.

### Verification and acceptance criteria

- A fresh environment can be restored from backup within the agreed RTO and RPO.
- Restore tests verify schema revision and data integrity, not only backup-file
  existence.
- Deployment and rollback drills complete successfully in staging.
- Alembic failures prevent traffic admission and have a tested recovery path.
- Runbooks identify prerequisites, commands, expected results, and escalation
  contacts/roles without embedding secrets.

## 8. Vulnerability scanning and dependency automation

### Objective

Continuously identify vulnerable Python dependencies, container packages,
images, leaked secrets, and unsafe source patterns, with an explicit remediation
process.

### Implementation tasks

- Enable automated dependency update pull requests for Python packages and
  GitHub Actions.
- Add software-composition analysis against `uv.lock` and built distributions.
- Scan the final container image and generate an SBOM.
- Add repository secret scanning and pre-commit developer guidance.
- Add static application-security analysis appropriate for Python and Docker.
- Pin CI actions and container base images by reviewed versions or digests and
  define an update cadence.
- Set severity thresholds, allowlist format, exception owner, expiry date, and
  remediation service levels.
- Verify licenses against an approved dependency policy.
- Protect the main branch so required security and quality checks cannot be
  bypassed without an audited exception.

### Verification and acceptance criteria

- Pull requests fail on unapproved critical/high vulnerabilities according to
  policy.
- Every release has a stored SBOM and image scan result.
- Dependency update pull requests run the full test/build suite.
- Exceptions are documented, time-bounded, and assigned to an owner.
- A seeded test secret is detected without exposing its full value.

## 9. Production-readiness completion gate

The roadmap is complete only when:

- each initiative's acceptance criteria are supported by automated evidence or
  a reviewed operational record;
- architecture and operating documents reflect the deployed implementation;
- failure modes have been tested, including Redis, telemetry, secrets, database,
  LLM provider, and deployment failures;
- the production threat model and data-governance review are approved; and
- an accountable owner accepts remaining risks.
