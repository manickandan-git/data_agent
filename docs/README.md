# Data Agent documentation

This directory contains the product and engineering design baseline for Data
Agent. The implementation and automated tests remain the source of truth when
documents and code disagree.

| Document | Purpose |
| --- | --- |
| [Product requirements](PRD.md) | Product goals, users, scope, requirements, and acceptance criteria |
| [Architecture](ARCHITECTURE.md) | System context, quality attributes, trust boundaries, and architecture decisions |
| [High-level design](HLD.md) | Major components, interfaces, workflows, and deployment topology |
| [Low-level design](LLD.md) | Modules, state transitions, validation rules, and implementation contracts |
| [Database design](DATABASE.md) | Relational model, data dictionary, constraints, indexes, and migration policy |
| [Production hardening roadmap](PRODUCTION_ROADMAP.md) | Deferred production initiatives, sequence, tasks, and acceptance criteria |

## Document ownership

- Product behavior changes should update `PRD.md`.
- Component, dependency, security-boundary, or deployment changes should update
  `ARCHITECTURE.md` and `HLD.md`.
- Module interfaces, workflow states, algorithms, and error behavior should
  update `LLD.md`.
- ORM or migration changes should update `DATABASE.md` in the same change set.
- Deferred production work and completion evidence should update
  `PRODUCTION_ROADMAP.md`.

Last reviewed against the implementation: 2026-09-07.
