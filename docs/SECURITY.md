# SECURITY — Orchestra Studio

**Version:** 0.1  
**Status:** Baseline security requirements

## 1. Security objectives

Protect:
- User files and operating system.
- Company and Agent data.
- Credentials and provider API keys.
- Artifacts and knowledge.
- Tool execution boundaries.
- Approval and audit integrity.
- Future remote worker connections.

Assume model output, tool input, imported files and external content may be malicious or malformed.

## 2. Trust boundaries

1. Electron Renderer ↔ Electron Main/Preload.
2. Desktop ↔ Local Backend.
3. Backend ↔ Worker.
4. Worker ↔ Runtime Provider.
5. Agent ↔ Tool Gateway.
6. Company/Department/Agent permission scopes.
7. Local machine ↔ Remote Control Plane/Worker in hybrid mode.

Validate data at every boundary. Do not rely on prompts as a security control.

## 3. Electron security

Required baseline:
- `contextIsolation: true`.
- `sandbox: true` where compatible with the chosen Electron configuration.
- `nodeIntegration: false`.
- Restrictive Content Security Policy.
- Validate IPC sender and payload schema.
- Expose only narrow, typed preload methods.
- Do not expose generic IPC, unrestricted filesystem, shell or process APIs.
- Restrict navigation and new-window creation.
- Keep Electron and dependencies updated.

Renderer should call backend APIs for business operations. It must not own database or filesystem access.

## 4. Permission model

Authorization scopes:
- Company.
- Department.
- Agent.
- Tool.

A permission decision should include principal, action, resource, scope and policy result. Default to deny when no rule grants access.

Tool action levels:

| Level | Meaning | Example |
|---|---|---|
| L0 Read | Read permitted data | Read a task or approved document |
| L1 Draft | Prepare but do not commit | Draft an email or file change |
| L2 Execute | Execute within a bounded workspace/sandbox | Write a file inside a task workspace |
| L3 External Action | Affect external systems or people | Send message, publish, purchase, delete remote data |

L3 requires explicit approval unless a future policy establishes a narrow, auditable exception. Do not allow an Agent to grant itself higher permissions.

## 5. Tool policy schema

Every tool should define:
- Tool ID and version.
- Input JSON schema.
- Required permission level.
- Allowed filesystem paths and/or domains.
- Timeout.
- CPU/memory/output limits where relevant.
- Network access policy.
- Approval requirement.
- Idempotency behavior.
- Audit fields.
- Error and cancellation behavior.

Tool Gateway is the enforcement point. A prompt saying “do not access other files” is not sufficient.

## 6. Secrets and credentials

- Never store API keys in Agent Definition JSON, source code, Git, logs or events.
- Store only credential references in ordinary database records.
- Resolve secrets only in the backend/worker at execution time.
- Prefer OS-backed secure storage for local desktop credentials.
- Redact secrets from exceptions and diagnostic output.
- Support credential revocation and rotation.
- Never send secret values to the renderer.

## 7. Local execution sandbox

For local Python or command execution:
- Use a dedicated workspace.
- Restrict filesystem access.
- Restrict environment variables.
- Apply timeouts and output limits.
- Avoid unrestricted shell access.
- Require explicit approval for operations outside the workspace.
- Do not execute untrusted repository code on the user's machine with full permissions.

A subprocess boundary alone is not a security sandbox. Document residual risks and use OS-level isolation where feasible.

## 8. Approval integrity

Approval records must include:
- Requested action and normalized parameters.
- Requesting Agent/Run/Task.
- Required permission.
- Human decision and timestamp.
- Decision note.
- Execution result linked to the approval.

Approval must bind to the exact action payload or its checksum. If the payload changes, require a new approval. Prevent replay and double execution through state checks and idempotency.

## 9. Audit and observability

Audit:
- Authentication/authorization decisions.
- Agent activation and configuration changes.
- Tool calls and policy decisions.
- Approval requests and decisions.
- Run lifecycle and cancellation.
- Credential reference changes.
- Worker registration and revocation.

Do not log secrets, private keys, full sensitive prompt context or unnecessary personal data.

## 10. Hybrid worker security (later phase)

- Mutual authentication or equivalent strong worker identity.
- Outbound authenticated TLS connection.
- Short-lived tokens/rotatable credentials.
- Worker registration and revocation.
- Assignment authorization and replay protection.
- Signed or integrity-checked artifacts where appropriate.
- Least-privilege worker process.
- Heartbeat and disconnect handling.
- No direct worker-to-database access.

## 11. Security test checklist

- Renderer cannot access Node APIs.
- Invalid IPC sender is rejected.
- Unauthorized company/department access is rejected.
- Tool path/domain restrictions are enforced server-side.
- L3 action cannot execute without valid approval.
- Modified approval payload is rejected.
- Secrets do not appear in logs/events/API responses.
- Runtime output is schema-validated.
- Worker cannot submit events for an unauthorized run.
- Cancellation and retry do not duplicate external side effects.
