import type { AgentCreate, ToolCreate } from "@orchestra/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { keys } from "./hooks";

export const keys1 = {
  org: (cid: string) => ["org", cid] as const,
  departments: (cid: string) => ["departments", cid] as const,
  skills: (cid: string) => ["skills", cid] as const,
  skillVersions: (sid: string) => ["skillVersions", sid] as const,
  agentSkills: (aid: string) => ["agentSkills", aid] as const,
  tools: (cid: string) => ["tools", cid] as const,
  toolAccess: (aid: string) => ["toolAccess", aid] as const,
  templates: ["templates"] as const,
};

const p = (company_id: string) => ({ params: { path: { company_id } } });
const pa = (agent_id: string) => ({ params: { path: { agent_id } } });

// ----- organization -----

export const useOrg = (cid: string) =>
  useQuery({ queryKey: keys1.org(cid), queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/org", p(cid))) });

export const useDepartments = (cid: string) =>
  useQuery({
    queryKey: keys1.departments(cid),
    queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/departments", p(cid))),
  });

function useOrgInvalidate(cid: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: keys1.org(cid) });
    qc.invalidateQueries({ queryKey: keys1.departments(cid) });
    qc.invalidateQueries({ queryKey: keys.agents(cid) });
    qc.invalidateQueries({ queryKey: ["agent"] });
    qc.invalidateQueries({ queryKey: ["toolAccess"] });
  };
}

export function useCreateDepartment(cid: string) {
  const inv = useOrgInvalidate(cid);
  return useMutation({
    mutationFn: async (body: { name: string; parent_department_id?: string | null; max_tool_level?: number | null }) =>
      unwrap(await api.POST("/api/v1/companies/{company_id}/departments", { ...p(cid), body })),
    onSuccess: inv,
  });
}

export function useUpdateDepartment(cid: string) {
  const inv = useOrgInvalidate(cid);
  return useMutation({
    mutationFn: async (v: {
      id: string;
      body: { name?: string; parent_department_id?: string | null; max_tool_level?: number | null };
    }) =>
      unwrap(
        await api.PATCH("/api/v1/departments/{department_id}", {
          params: { path: { department_id: v.id } },
          body: v.body,
        }),
      ),
    onSuccess: inv,
  });
}

export function useArchiveDepartment(cid: string) {
  const inv = useOrgInvalidate(cid);
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/api/v1/departments/{department_id}/archive", { params: { path: { department_id: id } } })),
    onSuccess: inv,
  });
}

export type AgentPatch = {
  name?: string;
  role?: string;
  description?: string;
  department_id?: string | null;
  reports_to_agent_id?: string | null;
};

export function useUpdateAgent(cid: string) {
  const inv = useOrgInvalidate(cid);
  return useMutation({
    mutationFn: async (v: { id: string; body: AgentPatch }) =>
      unwrap(await api.PATCH("/api/v1/agents/{agent_id}", { ...pa(v.id), body: v.body })),
    onSuccess: inv,
  });
}

export function useSaveLayout(cid: string) {
  return useMutation({
    mutationFn: async (positions: Record<string, { x: number; y: number }>) => {
      const r = await api.PUT("/api/v1/companies/{company_id}/org/layout", { ...p(cid), body: { positions } });
      if (!r.response.ok) unwrap(r);
    },
  });
}

export function useUpdateCompany(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name?: string; description?: string; max_tool_level?: number; max_parallel_runs?: number }) =>
      unwrap(await api.PATCH("/api/v1/companies/{company_id}", { ...p(cid), body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.company(cid) });
      qc.invalidateQueries({ queryKey: ["toolAccess"] });
    },
  });
}

// ----- agent versions -----

export function useCreateAgentVersion(cid: string, agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      definition: { instructions: string; goals?: string[] };
      runtime: { runtime_id: string; settings?: Record<string, unknown> };
    }) =>
      unwrap(await api.POST("/api/v1/agents/{agent_id}/versions", { ...pa(agentId), body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.agent(agentId) });
      qc.invalidateQueries({ queryKey: keys.versions(agentId) });
      qc.invalidateQueries({ queryKey: keys.agents(cid) });
    },
  });
}

// ----- skills -----

export const useSkills = (cid: string) =>
  useQuery({ queryKey: keys1.skills(cid), queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/skills", p(cid))) });

export const useSkillVersions = (sid: string | null) =>
  useQuery({
    queryKey: keys1.skillVersions(sid ?? "none"),
    enabled: !!sid,
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/{skill_id}/versions", { params: { path: { skill_id: sid! } } })),
  });

export function useCreateSkill(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; description: string; version: { instructions: string; input_hints: string[] } }) =>
      unwrap(await api.POST("/api/v1/companies/{company_id}/skills", { ...p(cid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys1.skills(cid) }),
  });
}

export function useCreateSkillVersion(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { skillId: string; instructions: string; input_hints: string[] }) =>
      unwrap(
        await api.POST("/api/v1/skills/{skill_id}/versions", {
          params: { path: { skill_id: v.skillId } },
          body: { instructions: v.instructions, input_hints: v.input_hints },
        }),
      ),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: keys1.skills(cid) });
      qc.invalidateQueries({ queryKey: keys1.skillVersions(v.skillId) });
      qc.invalidateQueries({ queryKey: ["agentSkills"] });
    },
  });
}

export const useAgentSkills = (aid: string) =>
  useQuery({ queryKey: keys1.agentSkills(aid), queryFn: async () => unwrap(await api.GET("/api/v1/agents/{agent_id}/skills", pa(aid))) });

export function useAttachSkill(aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { skill_id: string; skill_version_id?: string | null }) =>
      unwrap(await api.POST("/api/v1/agents/{agent_id}/skills", { ...pa(aid), body })),
    onSuccess: (data) => qc.setQueryData(keys1.agentSkills(aid), data),
  });
}

export function useDetachSkill(aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (skillId: string) =>
      unwrap(
        await api.DELETE("/api/v1/agents/{agent_id}/skills/{skill_id}", {
          params: { path: { agent_id: aid, skill_id: skillId } },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(keys1.agentSkills(aid), data),
  });
}

// ----- tools -----

export const useTools = (cid: string) =>
  useQuery({ queryKey: keys1.tools(cid), queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/tools", p(cid))) });

export function useCreateTool(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ToolCreate) => unwrap(await api.POST("/api/v1/companies/{company_id}/tools", { ...p(cid), body })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys1.tools(cid) });
      qc.invalidateQueries({ queryKey: ["toolAccess"] });
    },
  });
}

export function useArchiveTool(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.POST("/api/v1/tools/{tool_id}/archive", { params: { path: { tool_id: id } } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys1.tools(cid) });
      qc.invalidateQueries({ queryKey: ["toolAccess"] });
    },
  });
}

export const useToolAccess = (aid: string) =>
  useQuery({ queryKey: keys1.toolAccess(aid), queryFn: async () => unwrap(await api.GET("/api/v1/agents/{agent_id}/tool-access", pa(aid))) });

export function useGrantTool(aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (toolId: string) => unwrap(await api.POST("/api/v1/agents/{agent_id}/tools", { ...pa(aid), body: { tool_id: toolId } })),
    onSuccess: (data) => qc.setQueryData(keys1.toolAccess(aid), data),
  });
}

export function useRevokeTool(aid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (toolId: string) =>
      unwrap(
        await api.DELETE("/api/v1/agents/{agent_id}/tools/{tool_id}", {
          params: { path: { agent_id: aid, tool_id: toolId } },
        }),
      ),
    onSuccess: (data) => qc.setQueryData(keys1.toolAccess(aid), data),
  });
}

// ----- templates -----

export const useTemplates = () =>
  useQuery({ queryKey: keys1.templates, queryFn: async () => unwrap(await api.GET("/api/v1/templates")), staleTime: 60_000 });

export function useInstantiateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; name?: string }) =>
      unwrap(
        await api.POST("/api/v1/templates/company/{template_id}/instantiate", {
          params: { path: { template_id: v.id } },
          body: { name: v.name || null },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.companies }),
  });
}

export async function fetchAgentPreset(id: string) {
  return unwrap(await api.GET("/api/v1/templates/agent/{template_id}", { params: { path: { template_id: id } } }));
}

export type { AgentCreate };
