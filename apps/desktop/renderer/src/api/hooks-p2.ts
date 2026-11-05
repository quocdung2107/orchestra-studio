import type { TaskCreate } from "@orchestra/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { keys } from "./hooks";

export const keys2 = {
  approvals: (cid: string) => ["approvals", cid] as const,
  knowledge: (cid: string) => ["knowledge", cid] as const,
  search: (cid: string, q: string) => ["knowledge", cid, "search", q] as const,
  lessons: (cid: string) => ["lessons", cid] as const,
  proposals: (cid: string) => ["roleProposals", cid] as const,
};

const p = (company_id: string) => ({ params: { path: { company_id } } });
const pt = (task_id: string) => ({ params: { path: { task_id } } });
const pr = (run_id: string) => ({ params: { path: { run_id } } });

// ----- tasks & runs (P2) -----

export function useCreateTask(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TaskCreate) =>
      unwrap(await api.POST("/api/v1/companies/{company_id}/tasks", { ...p(cid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.tasks(cid) }),
  });
}

function useTaskCommand(cid: string, path: "/api/v1/tasks/{task_id}/cancel" | "/api/v1/tasks/{task_id}/retry") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => unwrap(await api.POST(path, pt(taskId))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tasks(cid) });
      qc.invalidateQueries({ queryKey: keys.runs(cid) });
    },
  });
}
export const useCancelTask = (cid: string) => useTaskCommand(cid, "/api/v1/tasks/{task_id}/cancel");
export const useRetryTask = (cid: string) => useTaskCommand(cid, "/api/v1/tasks/{task_id}/retry");

function useRunCommand(cid: string, path: "/api/v1/runs/{run_id}/pause" | "/api/v1/runs/{run_id}/resume") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (runId: string) => unwrap(await api.POST(path, pr(runId))),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: keys.run(r.id) });
      qc.invalidateQueries({ queryKey: keys.runs(cid) });
      qc.invalidateQueries({ queryKey: keys.tasks(cid) });
    },
  });
}
export const usePauseRun = (cid: string) => useRunCommand(cid, "/api/v1/runs/{run_id}/pause");
export const useResumeRun = (cid: string) => useRunCommand(cid, "/api/v1/runs/{run_id}/resume");

export function useSummarizeTask(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => unwrap(await api.POST("/api/v1/tasks/{task_id}/summarize", pt(taskId))),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.knowledge(cid) }),
  });
}

// ----- approvals -----

export const useApprovals = (cid: string) =>
  useQuery({
    queryKey: keys2.approvals(cid),
    queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/approvals", p(cid))),
  });

export function useDecideApproval(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; decision: "approve" | "reject"; checksum: string; note?: string }) =>
      unwrap(
        await api.POST("/api/v1/approvals/{approval_id}/decide", {
          params: { path: { approval_id: v.id } },
          body: { decision: v.decision, checksum: v.checksum, note: v.note ?? "" },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.approvals(cid) }),
  });
}

// ----- knowledge -----

export const useKnowledge = (cid: string) =>
  useQuery({
    queryKey: keys2.knowledge(cid),
    queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/knowledge", p(cid))),
  });

export const useKnowledgeSearch = (cid: string, q: string) =>
  useQuery({
    queryKey: keys2.search(cid, q),
    enabled: q.trim().length > 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/companies/{company_id}/knowledge/search", {
          params: { path: { company_id: cid }, query: { q } },
        }),
      ),
  });

export function useCreateNote(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title: string; content: string; kind?: "note" | "document" }) =>
      unwrap(await api.POST("/api/v1/companies/{company_id}/knowledge", { ...p(cid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.knowledge(cid) }),
  });
}

export function useUpdateNote(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; title?: string; content?: string }) =>
      unwrap(
        await api.PATCH("/api/v1/knowledge/{item_id}", {
          params: { path: { item_id: v.id } },
          body: { title: v.title ?? null, content: v.content ?? null },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.knowledge(cid) }),
  });
}

export function useArchiveNote(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/api/v1/knowledge/{item_id}/archive", { params: { path: { item_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.knowledge(cid) }),
  });
}

export function useArtifactToKnowledge(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (artifactId: string) =>
      unwrap(
        await api.POST("/api/v1/artifacts/{artifact_id}/to-knowledge", {
          params: { path: { artifact_id: artifactId } },
          body: {},
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.knowledge(cid) }),
  });
}

// ----- lessons & role proposals -----

export const useLessons = (cid: string) =>
  useQuery({
    queryKey: keys2.lessons(cid),
    queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/lessons", p(cid))),
  });

export function useProposeLesson(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title: string; lesson: string }) =>
      unwrap(await api.POST("/api/v1/companies/{company_id}/lessons", { ...p(cid), body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys2.lessons(cid) }),
  });
}

export function useReviewLesson(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; decision: "approve" | "reject"; note?: string }) =>
      unwrap(
        await api.POST("/api/v1/lessons/{lesson_id}/review", {
          params: { path: { lesson_id: v.id } },
          body: { decision: v.decision, note: v.note ?? "" },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys2.lessons(cid) });
      qc.invalidateQueries({ queryKey: keys2.knowledge(cid) });
    },
  });
}

export const useRoleProposals = (cid: string) =>
  useQuery({
    queryKey: keys2.proposals(cid),
    queryFn: async () => unwrap(await api.GET("/api/v1/companies/{company_id}/role-proposals", p(cid))),
  });

export function useReviewRoleProposal(cid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; decision: "approve" | "reject"; note?: string }) =>
      unwrap(
        await api.POST("/api/v1/role-proposals/{proposal_id}/review", {
          params: { path: { proposal_id: v.id } },
          body: { decision: v.decision, note: v.note ?? "" },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys2.proposals(cid) });
      qc.invalidateQueries({ queryKey: keys.agents(cid) });
    },
  });
}
