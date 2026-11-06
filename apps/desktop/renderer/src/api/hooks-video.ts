import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "@orchestra/contracts";
import { api, toApiError, unwrap } from "./client";

export type Project = components["schemas"]["ProjectOut"];
export type Scene = components["schemas"]["SceneOut"];
export type Render = components["schemas"]["RenderOut"];
export type MediaSettings = components["schemas"]["MediaSettings"];
export type VoiceProfile = components["schemas"]["VoiceProfileOut"];
export type ScriptIn = components["schemas"]["ScriptIn"];

export const keysVideo = {
  projects: (cid: string) => ["video-projects", cid] as const,
  project: (id: string) => ["video-project", id] as const,
  samples: ["video-samples"] as const,
  settings: (cid: string) => ["media-settings", cid] as const,
  voices: (cid: string) => ["voice-profiles", cid] as const,
  engines: ["media-engines"] as const,
  providers: ["media-providers"] as const,
};

/** Same-origin URL; the Electron shell / Vite proxy adds the token (ADR-0009). */
export const assetUrl = (id: string, download = false) =>
  `/api/v1/assets/${id}/content${download ? "?download=true" : ""}`;

export async function uploadAsset(companyId: string, kind: "image" | "music" | "reference_audio", file: File) {
  const url = `/api/v1/companies/${companyId}/assets?kind=${kind}&label=${encodeURIComponent(file.name)}`;
  const res = await fetch(url, { method: "PUT", body: file });
  const body = await res.json().catch(() => undefined);
  if (!res.ok) throw toApiError(res.status, body);
  return body as components["schemas"]["AssetOut"];
}

export const useVideoSamples = () =>
  useQuery({ queryKey: keysVideo.samples, queryFn: async () => unwrap(await api.GET("/api/v1/video-samples")) });

export const useVideoProjects = (cid: string) =>
  useQuery({
    queryKey: keysVideo.projects(cid),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/companies/{company_id}/video-projects", { params: { path: { company_id: cid } } })),
  });

export const useVideoProject = (id: string | null) =>
  useQuery({
    queryKey: keysVideo.project(id ?? ""),
    enabled: !!id,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/video-projects/{project_id}", { params: { path: { project_id: id! } } })),
    // Poll while something is running in the background.
    refetchInterval: (q) => {
      const d = q.state.data as Project | undefined;
      const busy = d && (d.status === "producing" || d.jobs.some((j) => j.status === "queued" || j.status === "running"));
      return busy ? 1500 : false;
    },
  });

export function useProjectAction<T>(projectId: string, fn: (arg: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: keysVideo.project(projectId) }),
  });
}

export const useCreateProject = (cid: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (script: ScriptIn) =>
      unwrap(
        await api.POST("/api/v1/companies/{company_id}/video-projects", {
          params: { path: { company_id: cid } },
          body: { script },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keysVideo.projects(cid) }),
  });
};

export const useMediaSettings = (cid: string) =>
  useQuery({
    queryKey: keysVideo.settings(cid),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/companies/{company_id}/media-settings", { params: { path: { company_id: cid } } })),
  });

export const useSaveMediaSettings = (cid: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: MediaSettings) =>
      unwrap(
        await api.PUT("/api/v1/companies/{company_id}/media-settings", { params: { path: { company_id: cid } }, body }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keysVideo.settings(cid) }),
  });
};

export const useVoiceProfiles = (cid: string) =>
  useQuery({
    queryKey: keysVideo.voices(cid),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/companies/{company_id}/voice-profiles", { params: { path: { company_id: cid } } })),
  });

export const useUpdateVoiceProfile = (cid: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; body: components["schemas"]["VoiceSettings"] }) =>
      unwrap(await api.PUT("/api/v1/voice-profiles/{profile_id}", { params: { path: { profile_id: v.id } }, body: v.body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keysVideo.voices(cid) }),
  });
};

export const useEngines = () =>
  useQuery({
    queryKey: keysVideo.engines,
    queryFn: async () => unwrap(await api.GET("/api/v1/media/engines")),
    refetchInterval: 10_000,
  });

export const useProviders = () =>
  useQuery({ queryKey: keysVideo.providers, queryFn: async () => unwrap(await api.GET("/api/v1/media/providers")) });

export const fetchVoices = async (provider: "vieneu" | "zerotts" | "fake_tts") =>
  unwrap(await api.GET("/api/v1/media/tts/{provider_id}/voices", { params: { path: { provider_id: provider } } }));

export const previewNormalize = async (text: string, dialect: "south" | "north", lexicon: Record<string, string>) =>
  unwrap(await api.POST("/api/v1/voice/normalize-preview", { body: { text, dialect, lexicon, max_chars: 180 } }));
