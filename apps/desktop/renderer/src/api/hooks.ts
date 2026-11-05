import type { AgentCreate, CompanyCreate } from "@orchestra/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";

export const keys = {
  health: ["health"] as const,
  companies: ["companies"] as const,
  company: (id: string) => ["company", id] as const,
  agents: (cid: string) => ["agents", cid] as const,
  agent: (id: string) => ["agent", id] as const,
  versions: (id: string) => ["versions", id] as const,
  tasks: (cid: string) => ["tasks", cid] as const,
  runs: (cid: string) => ["runs", cid] as const,
  run: (id: string) => ["run", id] as const,
  runEvents: (id: string) => ["runEvents", id] as const,
  runtimes: ["runtimes"] as const,
  scenarios: ["scenarios"] as const,
};

export const useHealth = () =>
  useQuery({
    queryKey: keys.health,
    queryFn: async () => unwrap(await api.GET("/api/v1/health")),
    refetchInterval: 10_000,
  });

export const useCompanies = () =>
  useQuery({
    queryKey: keys.companies,
    queryFn: async () => unwrap(await api.GET("/api/v1/companies")),
  });

export const useCompany = (id: string) =>
  useQuery({
    queryKey: keys.company(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/companies/{company_id}", { params: { path: { company_id: id } } })),
  });

export const useAgents = (cid: string) =>
  useQuery({
    queryKey: keys.agents(cid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/companies/{company_id}/agents", {
          params: { path: { company_id: cid } },
        }),
      ),
  });

export const useAgent = (id: string) =>
  useQuery({
    queryKey: keys.agent(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/agents/{agent_id}", { params: { path: { agent_id: id } } })),
  });

export const useAgentVersions = (id: string) =>
  useQuery({
    queryKey: keys.versions(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/agents/{agent_id}/versions", { params: { path: { agent_id: id } } }),
      ),
  });

export const useTasks = (cid: string) =>
  useQuery({
    queryKey: keys.tasks(cid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/companies/{company_id}/tasks", {
          params: { path: { company_id: cid } },
        }),
      ),
  });

export const useRuns = (cid: string) =>
  useQuery({
    queryKey: keys.runs(cid),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/companies/{company_id}/runs", {
          params: { path: { company_id: cid } },
        }),
      ),
  });

export const useRun = (id: string) =>
  useQuery({
    queryKey: keys.run(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/runs/{run_id}", { params: { path: { run_id: id } } })),
  });

export const useRunEvents = (cid: string, runId: string) =>
  useQuery({
    queryKey: keys.runEvents(runId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/companies/{company_id}/events", {
          params: { path: { company_id: cid }, query: { run_id: runId, limit: 1000 } },
        }),
      ),
  });

export const useRuntimes = () =>
  useQuery({
    queryKey: keys.runtimes,
    queryFn: async () => unwrap(await api.GET("/api/v1/runtimes")),
    staleTime: Infinity,
  });

export const useScenarios = () =>
  useQuery({
    queryKey: keys.scenarios,
    queryFn: async () => unwrap(await api.GET("/api/v1/scenarios")),
    staleTime: Infinity,
  });

export async function fetchArtifactText(id: string): Promise<string> {
  const res = await fetch(`/api/v1/artifacts/${encodeURIComponent(id)}/content`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

// ----- mutations: UI shows the backend's answer, never an optimistic fake -----

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CompanyCreate) =>
      unwrap(await api.POST("/api/v1/companies", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.companies }),
  });
}

export function useSeedDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/demo/seed")),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.companies }),
  });
}

export function useCreateAgent(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: AgentCreate) =>
      unwrap(
        await api.POST("/api/v1/companies/{company_id}/agents", {
          params: { path: { company_id: cid } },
          body,
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.agents(cid) }),
  });
}

export type AgentAction = "activate" | "deactivate" | "archive";

export function useAgentAction(cid: string, agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (action: AgentAction) => {
      const opts = { params: { path: { agent_id: agentId } } };
      if (action === "activate") return unwrap(await api.POST("/api/v1/agents/{agent_id}/activate", opts));
      if (action === "deactivate")
        return unwrap(await api.POST("/api/v1/agents/{agent_id}/deactivate", opts));
      return unwrap(await api.POST("/api/v1/agents/{agent_id}/archive", opts));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.agents(cid) });
      qc.invalidateQueries({ queryKey: keys.agent(agentId) });
    },
  });
}

export function useStartScenario(cid: string) {
  return useMutation({
    mutationFn: async (scenarioId: string) =>
      unwrap(
        await api.POST("/api/v1/companies/{company_id}/scenarios/{scenario_id}/start", {
          params: { path: { company_id: cid, scenario_id: scenarioId } },
        }),
      ),
  });
}
