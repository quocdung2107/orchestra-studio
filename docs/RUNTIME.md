# RUNTIME — Orchestra Studio

**Version:** 0.1  
**Status:** Baseline runtime contract

## 1. Separation of concerns

An Agent Definition describes what an Agent is. A Runtime executes a particular run. A Worker hosts or brokers execution.

- Agent Definition: role, instructions, skills, permitted tools, configuration.
- Runtime Adapter: provider-specific execution implementation.
- Agent Run: one execution instance.
- Worker: process/machine responsible for running an adapter.
- Orchestrator: schedules work and owns lifecycle decisions.

Changing runtime should not require recreating the Agent or rewriting task orchestration.

## 2. Runtime tiers

| Tier | Runtime | Purpose | API cost |
|---|---|---|---|
| L0 | Mock/Simulated | Deterministic scenario tests and UI development | None |
| L1 | Local model (e.g. Ollama) | Run a model on the user's machine | No provider API fee; uses local resources |
| L2 | Cloud provider | Claude/OpenAI/other APIs | Usage-based/provider pricing |

Implement L0 first. Do not require a model download or API key to run the initial demo.

## 3. Adapter contract

A conceptual Python interface:

```python
from typing import AsyncIterator, Protocol

class AgentRuntime(Protocol):
    async def execute(
        self,
        run_id: str,
        agent_config: dict,
        task: dict,
        context: dict,
    ) -> AsyncIterator[dict]:
        ...

    async def cancel(self, run_id: str) -> bool:
        ...

    async def resume(
        self,
        run_id: str,
        resume_data: dict,
    ) -> AsyncIterator[dict]:
        ...

    async def health_check(self) -> dict:
        ...
```

This is a conceptual contract, not a requirement that every runtime support every operation. Define runtime capabilities explicitly, for example:
- `supports_streaming`
- `supports_cancel`
- `supports_pause`
- `supports_resume`
- `supports_tool_calls`
- `supports_structured_output`
- `supports_checkpointing`

The orchestrator must check capabilities before offering an action. Unsupported actions must return a clear result.

## 4. Normalized runtime event types

Adapters translate provider-specific output into normalized events, such as:
- `run.started`
- `run.progress`
- `run.message`
- `run.tool_call.requested`
- `run.tool_call.started`
- `run.tool_call.completed`
- `run.approval.required`
- `run.artifact.produced`
- `run.completed`
- `run.failed`
- `run.cancelled`

Provider-specific raw data may be retained in bounded diagnostic metadata only when safe and useful. Never persist secrets or hidden reasoning.

## 5. L0 Mock Runtime requirements

Mock Runtime must not be a fake dashboard-only log generator.

It must pass through the same:
- Task Engine.
- Agent Manager.
- Orchestrator.
- Runtime Manager.
- Event persistence/delivery.
- Approval system.
- Artifact handling.
- Metrics pipeline where applicable.

Scenario definitions should be deterministic and replayable. Initial demo organization: **Demo Video Studio**, with roles such as:
- CEO
- CMO
- Researcher
- Strategist
- Scriptwriter
- Producer
- Reviewer
- Secretary

Scenarios should cover:
1. Delegation between Agents.
2. Sequential tasks.
3. Parallel tasks.
4. Failure and retry.
5. Approval request and approval/rejection.
6. Artifact creation.
7. Lesson/knowledge capture.
8. KPI/metric updates.
9. Agent unavailable or runtime error.
10. Repeated run producing the same expected event sequence, subject to generated IDs/timestamps.

Mock scenarios must make it possible to stress-test 10, 20 and 50 Agents without calling an AI API. Keep scenario timing configurable; tests should use fast virtual/deterministic progression rather than long sleeps.

## 6. Local Python Runtime

A constrained runtime for local deterministic Python tasks may be useful, but it must not execute arbitrary code with unrestricted access. Define:
- allowed task types,
- working directory,
- filesystem boundaries,
- timeout,
- environment variables,
- resource limits,
- subprocess policy,
- output size limits.

Do not treat a local Python process as automatically safe.

## 7. Ollama adapter

Ollama is a later phase. Keep its adapter isolated. Do not assume OpenAI-compatible endpoints imply complete feature parity with the OpenAI SDK or other agent frameworks.

Consider local hardware constraints:
- Model memory footprint.
- GPU/CPU/RAM availability.
- One shared model with a queue may be preferable to several heavy models loaded simultaneously.
- Expose runtime health and model availability to the dashboard.

## 8. Cloud adapters

Claude and OpenAI adapters are later phase integrations. Normalize their outputs and capabilities through the adapter boundary. Do not leak SDK-specific objects into domain models or frontend types.

Credentials:
- Resolve secret references at execution time.
- Never return secret values to the renderer.
- Redact secrets from logs, events and exceptions.
- Allow per-company/provider credential policies.

## 9. Worker lifecycle and hybrid readiness

Local first:
- Backend starts or supervises local worker.
- Worker registers capabilities and health.
- Orchestrator dispatches eligible runs.
- Worker sends normalized events/results.

Hybrid later:
- Worker has stable identity and authentication.
- Worker connects outbound to Control Plane over authenticated transport.
- Worker receives only authorized assignments.
- Worker reports heartbeat, capabilities and execution events.
- Worker does not access the Control Plane database directly.
- Artifact transfer uses authorized, bounded upload/download mechanisms.
- Disconnects and retries must not silently mark a run complete.

## 10. Retry and idempotency

- Distinguish retryable and non-retryable failures.
- Bound retry count and use backoff.
- Record every attempt.
- Ensure tool actions are idempotent where possible.
- External side effects require approval/policy and idempotency keys.
- Never blindly retry an external action whose outcome is unknown.
