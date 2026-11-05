# IMPLEMENTATION PLAN — Orchestra Studio

**Version:** 0.1  
**Status:** Initial delivery plan

## 1. Delivery principles

- Implement vertical slices that can be run and tested.
- Complete P0 before adding real model integrations.
- Keep each TASK small enough to review.
- Do not create every planned directory in advance.
- Every TASK specifies allowed files, tests and completion criteria.
- Update docs/ADRs when a decision changes.

## 2. Phases

| Phase | Goal | Main deliverables |
|---|---|---|
| P0 | Foundation & Dashboard Shell | Electron, React, FastAPI, DB, Company, Agent Definition, Mock Runtime, Events, SSE |
| P1 | Organization & Agent Manager | Org Builder, templates, versions, skills, tools |
| P2 | Task Orchestration | Dependencies, assignment, parallel work, retries, pause/resume/cancel, approvals |
| P3 | Knowledge & Secretary | Knowledge index/search, summaries, lessons, role-change proposals |
| P4 | KPI & Multi-Runtime | Metrics, Ollama, Claude/OpenAI adapters, credential management |
| P5 | Hybrid Deployment | Remote workers, identity, auth, sandbox, backup/recovery |

## 3. P0 task sequence

### P0-01 — Repository & project setup

Goal:
- Establish a reproducible monorepo and developer workflow.

In scope:
- Inspect current repository first.
- Set up only necessary desktop/backend/package skeleton.
- Add formatting/lint/test commands.
- Add `.gitignore`, environment example without secrets, README development instructions.

Out of scope:
- Business features.
- Runtime integration.
- Full UI design system.

Completion:
- Clean install/build instructions work on Windows.
- Desktop and backend can be started independently.
- No secrets or runtime data committed.
- Baseline tests pass.

### P0-02 — Database foundation

In scope:
- SQLAlchemy 2.x setup.
- Alembic.
- SQLite connection/session lifecycle.
- Initial migration for companies and minimal foundational metadata.
- Health/connection test.

Out of scope:
- Full schema for all future modules.
- PostgreSQL deployment.
- Event sourcing framework.

Completion:
- Fresh DB can be migrated.
- Tests create isolated temporary DB.
- Foreign keys and transaction behavior are configured.
- No business logic in ORM models.

### P0-03 — FastAPI foundation

In scope:
- App factory and versioned `/api/v1`.
- Settings/config handling.
- Dependency injection for DB session.
- Error response conventions.
- Health endpoint.
- OpenAPI generation.

Out of scope:
- Full auth system if single-user local MVP has not defined it.
- Agent execution endpoints.

Completion:
- Backend starts reliably.
- Health endpoint and API tests pass.
- Errors are structured and secrets are not leaked.

### P0-04 — Electron foundation

In scope:
- Electron main/preload/renderer bootstrap.
- Secure BrowserWindow defaults.
- Typed, narrow IPC example only if required.
- Backend lifecycle/connection strategy.

Out of scope:
- Broad native filesystem or shell access.
- Business features.

Completion:
- Desktop starts on Windows.
- Renderer has no direct Node integration.
- Security configuration is tested/reviewed.

### P0-05 — Dashboard shell

In scope:
- Sidebar/workspace/inspector/activity-console layout.
- Navigation placeholders for planned modules.
- Responsive desktop layout and collapsible inspector/console.
- Typed API client and query setup.

Out of scope:
- Fake Agent activity.
- Full organization graph editor.
- Analytics implementation.

Completion:
- App has a coherent Control Center shell.
- Loading/empty/error states exist.
- UI does not invent live state.

### P0-06 — Company Manager

In scope:
- Company create/list/detail/update basics.
- Backend validation and persistence.
- Company Overview minimal view.

Out of scope:
- Multi-tenant SaaS auth.
- Billing.
- Department graph.

Completion:
- CRUD behavior is tested.
- Invalid inputs return structured errors.
- UI reflects backend state.

### P0-07 — Agent Definition

In scope:
- Provider-neutral Agent Definition.
- Agent create/list/detail/update and activation status.
- Version snapshot for definition changes.
- Runtime preference reference without secrets.

Out of scope:
- Real model execution.
- Skill marketplace.
- Advanced permission editor.

Completion:
- Agent Definition persists independently of runtime.
- Version history is preserved.
- API/UI schema does not expose secrets.

### P0-08 — Mock Runtime

In scope:
- Runtime adapter interface and registry.
- Deterministic Mock Runtime.
- Demo Video Studio scenario.
- Normalized progress/result/failure events.

Out of scope:
- Ollama/Claude/OpenAI.
- Arbitrary code execution.
- Real external tool integrations.

Completion:
- Scenario can execute without API keys or model downloads.
- It uses the same orchestration/event pathway intended for real runtimes.
- Repeated scenario tests produce equivalent logical outcomes.
- Failure scenario is observable.

### P0-09 — Event System

In scope:
- Versioned event envelope.
- Event persistence.
- Event query endpoint.
- Append-only behavior.
- Basic event validation and ordering.

Out of scope:
- Distributed event broker.
- Complex event sourcing.
- Cross-region delivery.

Completion:
- Events survive app restart.
- Event order is deterministic within defined stream.
- Invalid payloads are rejected.
- Event records cannot be silently overwritten.

### P0-10 — Live Dashboard

In scope:
- SSE event stream.
- Company-scoped subscription for local MVP.
- Live activity console.
- Agent/Run status refresh.
- Reconnect and duplicate handling.

Out of scope:
- Remote worker networking.
- WebSocket terminal.
- Advanced analytics.

Completion:
- Mock scenario updates dashboard in real time.
- Reconnect does not corrupt UI state.
- UI distinguishes requested, pending and confirmed actions.
- No fake success state.

## 4. P0 acceptance scenario

A user should be able to:

1. Launch Orchestra Studio locally without an AI API key.
2. Create a Company.
3. Create several Agent Definitions.
4. Load or create the Demo Video Studio scenario.
5. Start a Mock Run.
6. Observe normalized events in the Activity Console.
7. See Agent/Run status update from backend state.
8. Inspect the task/run result and artifact metadata.
9. Trigger a deterministic failure scenario and inspect the failure.
10. Restart the app and inspect persisted Company, Agents and event history.

The scenario is not complete if the dashboard merely plays hardcoded logs without backend execution.

## 5. Later-phase acceptance highlights

P1:
- Organization graph persists and supports edit/validation.
- Skills and tools are versioned/permission-aware.

P2:
- Dependencies, parallel execution, retries and approvals are real backend behavior.
- Cancellation/pause/resume reflect runtime capabilities.

P3:
- Knowledge items retain provenance.
- Lessons can be reviewed/approved before being promoted to reusable knowledge.

P4:
- Provider adapters pass contract tests.
- Usage/cost data is labeled with source and confidence.
- Local model resource limits are visible.

P5:
- Remote worker identity, authorization, heartbeat and revocation work.
- Network interruption does not falsely complete a run.
- Artifacts transfer securely.

## 6. Task template

```markdown
# TASK-ID — Short title

## Goal
One measurable outcome.

## Context
Relevant architecture and current repo state.

## In scope
- ...

## Out of scope
- ...

## Allowed files
- ...

## Inputs / Outputs
- Input:
- Output:

## Contracts
- API:
- Database:
- Events:
- Runtime:

## Completion criteria
- [ ] ...

## Required tests
- [ ] ...

## Commands
- ...

## Risks / rollback
- ...

## Final report
- Files changed:
- Tests run and results:
- Known limitations:
- Follow-up:
```

## 7. Definition of Done

A task is done only when:
- Scope is respected.
- Tests pass and their commands/results are reported.
- Error paths are handled.
- Contracts and docs are updated when needed.
- No secrets or generated runtime data are committed.
- Diff is reviewed for unrelated changes.
- Remaining limitations are stated honestly.

## 8. Decision log

Use `docs/adr/` for decisions that affect:
- Module boundaries.
- Database relationships or migration policy.
- Event envelope/ordering/consistency.
- Runtime interface/capabilities.
- Security and permission boundaries.
- Deployment topology.
- Major dependencies.

Do not silently rewrite the baseline.
