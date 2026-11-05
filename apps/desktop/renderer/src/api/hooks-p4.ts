import type { CredentialCreate } from "@orchestra/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";

export const keys4 = {
  credentials: ["credentials"] as const,
  secretStore: ["secretStore"] as const,
  health: (rid: string) => ["runtimeHealth", rid] as const,
  kpis: (cid: string, days: number) => ["kpis", cid, days] as const,
};

const pc = (credential_id: string) => ({ params: { path: { credential_id } } });

// ----- credentials (ADR-0021): the API never returns secret values -----

export const useCredentials = () =>
  useQuery({ queryKey: keys4.credentials, queryFn: async () => unwrap(await api.GET("/api/v1/credentials")) });

export const useSecretStore = () =>
  useQuery({ queryKey: keys4.secretStore, queryFn: async () => unwrap(await api.GET("/api/v1/secret-store")) });

function useCredentialMutation<T>(fn: (arg: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: keys4.credentials }) });
}

export const useCreateCredential = () =>
  useCredentialMutation(async (body: CredentialCreate) => unwrap(await api.POST("/api/v1/credentials", { body })));

export const useRotateCredential = () =>
  useCredentialMutation(async ({ id, secret }: { id: string; secret: string }) =>
    unwrap(await api.POST("/api/v1/credentials/{credential_id}/rotate", { ...pc(id), body: { secret } })),
  );

export const useRevokeCredential = () =>
  useCredentialMutation(async (id: string) => unwrap(await api.POST("/api/v1/credentials/{credential_id}/revoke", pc(id))));

export const useVerifyCredential = () =>
  useCredentialMutation(async (id: string) => unwrap(await api.POST("/api/v1/credentials/{credential_id}/verify", pc(id))));

// ----- runtimes & KPIs -----

export type OllamaHealth = {
  status: string;
  detail?: string;
  base_url?: string;
  version?: string;
  limits?: { max_concurrency: number; running: number; waiting: number };
  models?: { name: string; size_bytes?: number; parameter_size?: string; quantization?: string }[];
  loaded?: { name: string; size_bytes?: number; vram_bytes?: number; expires_at?: string; context_length?: number }[];
};

export const useRuntimeHealth = (runtimeId: string, enabled = true) =>
  useQuery({
    queryKey: keys4.health(runtimeId),
    enabled,
    refetchInterval: 15_000,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/runtimes/{runtime_id}/health", { params: { path: { runtime_id: runtimeId } } })) as OllamaHealth,
  });

export const useKpis = (cid: string, days: number) =>
  useQuery({
    queryKey: keys4.kpis(cid, days),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/companies/{company_id}/kpis", { params: { path: { company_id: cid }, query: { days } } })),
  });
