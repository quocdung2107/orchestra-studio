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
