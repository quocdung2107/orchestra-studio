import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";

export const keys5 = { backups: ["backups"] as const };

// ----- backups (ADR-0027): restore is a CLI step while the app is closed -----

export const useBackups = () =>
  useQuery({ queryKey: keys5.backups, queryFn: async () => unwrap(await api.GET("/api/v1/backups")) });

export const useCreateBackup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/backups")),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys5.backups }),
  });
};

// ----- workers (ADR-0025) -----

export const keysWorkers = ["workers"] as const;

export const useWorkers = () =>
  useQuery({
    queryKey: keysWorkers,
    queryFn: async () => unwrap(await api.GET("/api/v1/workers")),
    refetchInterval: 10_000,
  });

export const useCreatePairing = () =>
  useMutation({
    mutationFn: async (name: string) => unwrap(await api.POST("/api/v1/workers/pairing-codes", { body: { name } })),
  });

export const useRevokeWorker = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (worker_id: string) =>
      unwrap(await api.POST("/api/v1/workers/{worker_id}/revoke", { params: { path: { worker_id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keysWorkers }),
  });
};
