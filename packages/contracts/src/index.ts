// Generated types live in api.d.ts (run `pnpm contracts` to refresh).
import type { components, paths } from "./api";

export type { components, paths };
type S = components["schemas"];

export type Company = S["CompanyOut"];
export type CompanyCreate = S["CompanyCreate"];
export type Agent = S["AgentOut"];
export type AgentDetail = S["AgentDetail"];
export type AgentCreate = S["AgentCreate"];
export type AgentVersion = S["AgentVersionOut"];
export type Task = S["TaskOut"];
export type Run = S["RunOut"];
export type RunDetail = S["RunDetail"];
export type Artifact = S["ArtifactOut"];
export type EventEnvelope = S["EventOut"];
export type RuntimeInfo = S["RuntimeInfo"];
export type ScenarioInfo = S["ScenarioInfo"];
export type ApiError = S["ErrorResponse"];
