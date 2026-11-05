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
export type Department = S["DepartmentOut"];
export type OrgGraph = S["OrgGraph"];
export type OrgAgentNode = S["OrgAgentNode"];
export type Skill = S["SkillDetail"];
export type SkillVersion = S["SkillVersionOut"];
export type AgentSkill = S["AgentSkillOut"];
export type Tool = S["ToolOut"];
export type ToolCreate = S["ToolCreate"];
export type AccessDecision = S["AccessDecision"];
export type TemplateInfo = S["TemplateInfo"];
export type AgentPreset = S["AgentPreset"];
export type TaskCreate = S["TaskCreate"];
export type Approval = S["ApprovalOut"];
export type KnowledgeItem = S["KnowledgeOut"];
export type SearchResult = S["SearchResult"];
export type Lesson = S["LessonOut"];
export type RoleProposal = S["RoleProposalOut"];
