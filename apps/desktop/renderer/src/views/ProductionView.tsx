import { useRef, useState } from "react";
import { api, errorMessage, toApiError, unwrap } from "../api/client";
import {
  assetUrl,
  uploadAsset,
  useCreateProject,
  useProjectAction,
  useVideoProject,
  useVideoProjects,
  useVideoSamples,
  type Project,
  type Scene,
  type ScriptIn,
} from "../api/hooks-video";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge, inputClass } from "../components/ui";

/** Video production from a script (ADR-0033): image source chooser, scenes, voice, render, QA. */
export function ProductionView({ companyId }: { companyId: string }) {
  const [openId, setOpenId] = useState<string | null>(null);
  if (openId) return <ProjectDetail projectId={openId} companyId={companyId} onBack={() => setOpenId(null)} />;
  return <ProjectList companyId={companyId} onOpen={setOpenId} />;
}

function ProjectList({ companyId, onOpen }: { companyId: string; onOpen: (id: string) => void }) {
  const list = useVideoProjects(companyId);
  const samples = useVideoSamples();
  const create = useCreateProject(companyId);
  const [json, setJson] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const createFrom = (script: ScriptIn) => create.mutate(script, { onSuccess: (p) => onOpen(p.id) });
  const createFromJson = () => {
    try {
      setJsonError(null);
      createFrom(JSON.parse(json) as ScriptIn);
    } catch (e) {
      setJsonError(`JSON không hợp lệ: ${errorMessage(e)}`);
    }
  };

  if (list.isLoading) return <Loading />;
  if (list.isError) return <ErrorView error={list.error} onRetry={() => list.refetch()} />;
  return (
    <div className="max-w-4xl">
      <Section title="Sản xuất video">
        {list.data!.length === 0 ? (
          <Empty>Chưa có video nào. Tạo từ kịch bản mẫu hoặc dán kịch bản JSON bên dưới.</Empty>
        ) : (
          <ul className="divide-y divide-slate-800" data-testid="video-project-list">
            {list.data!.map((p) => (
              <li key={p.id} className="py-2 flex items-center justify-between gap-3">
                <button className="text-left hover:underline" onClick={() => onOpen(p.id)}>
                  {p.title}
                  <span className="ml-2 text-xs text-slate-400">{p.profile === "short" ? "Reels 9:16" : "Video dài 16:9"}</span>
                </button>
                <StatusBadge status={p.status} />
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="Tạo video mới">
        {create.isError && <ErrorView error={create.error} />}
        <div className="flex flex-wrap gap-2 mb-3">
          {(samples.data ?? []).map((s) => (
            <SecondaryButton key={s.id} disabled={create.isPending} onClick={() => createFrom(s.script)}>
              Mẫu: {s.script.title}
            </SecondaryButton>
          ))}
        </div>
        <textarea
          className={`${inputClass} font-mono h-32`}
          placeholder='{"title": "...", "profile": "short", "scenes": [{"narration": "...", "visual_prompt": "..."}]}'
          value={json}
          onChange={(e) => setJson(e.target.value)}
          aria-label="Kịch bản JSON"
        />
        {jsonError && <p className="text-sm text-red-300 mt-1">{jsonError}</p>}
        <Button className="mt-2" disabled={!json.trim() || create.isPending} onClick={createFromJson}>
          Tạo từ kịch bản JSON
        </Button>
        <p className="text-xs text-slate-500 mt-2">Viết kịch bản bằng Claude sẽ có ở bước sau (đã chọn Claude cho kịch bản).</p>
      </Section>
    </div>
  );
}

const post = async (path: string, body: unknown = {}) => {
  const res = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => undefined);
  if (!res.ok) throw toApiError(res.status, data);
  return data;
};

export function ProjectDetail({ projectId, companyId, onBack }: { projectId: string; companyId: string; onBack: () => void }) {
  const q = useVideoProject(projectId);
  const setSource = useProjectAction(projectId, (source: "manual" | "cloud") =>
    post(`/api/v1/video-projects/${projectId}/image-source`, { source }),
  );
  const produce = useProjectAction(projectId, (allow_placeholders: boolean) =>
    post(`/api/v1/video-projects/${projectId}/produce`, { allow_placeholders }),
  );
  const retry = useProjectAction(projectId, () => post(`/api/v1/video-projects/${projectId}/retry`));
  const genAll = useProjectAction(projectId, () => post(`/api/v1/video-projects/${projectId}/images`, { mode: "cloud" }));

  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorView error={q.error} onRetry={() => q.refetch()} />;
  const p = q.data!;
  const missing = p.scenes.filter((s) => !s.image_asset_id).length;
  const busy = p.status === "producing";
  const actionError = setSource.error ?? produce.error ?? retry.error ?? genAll.error;

  return (
    <div className="max-w-4xl min-w-0">
      <button className="text-sm text-slate-400 hover:underline mb-2" onClick={onBack}>
        ← Danh sách video
      </button>
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-lg font-semibold">{p.title}</h1>
        <StatusBadge status={p.status} />
      </div>
      <p className="text-sm text-slate-400 mb-4">
        {p.profile === "short" ? "Reels 9:16" : "Video dài 16:9"} · giọng: {p.voice_profile_name} · ước tính{" "}
        {Math.round(p.estimated_duration_s)} giây (cho phép {p.profile_limits.min_s}–{p.profile_limits.max_s} giây)
      </p>
      {p.last_error && (
        <div className="mb-3 p-2 rounded bg-red-950 border border-red-800 text-sm text-red-200">
          {p.last_error}
          <SecondaryButton className="ml-3" onClick={() => retry.mutate(undefined)}>
            Thử lại
          </SecondaryButton>
        </div>
      )}
      {actionError && <ErrorView error={actionError} />}

      {!p.image_source ? (
        <ImageSourceChooser onChoose={(s) => setSource.mutate(s)} pending={setSource.isPending} />
      ) : (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span>
            Nguồn ảnh: <b>{p.image_source === "manual" ? "Nhập tay" : "AI cloud"}</b>
          </span>
          <SecondaryButton
            onClick={() => {
              const next = p.image_source === "manual" ? "cloud" : "manual";
              if (confirm(`Đổi nguồn ảnh sang ${next === "manual" ? "nhập tay" : "AI cloud"}? Ảnh đã có vẫn giữ.`))
                setSource.mutate(next);
            }}
          >
            Đổi nguồn ảnh
          </SecondaryButton>
          {p.image_source === "cloud" && (
            <SecondaryButton disabled={genAll.isPending || missing === 0} onClick={() => genAll.mutate(undefined)}>
              Tạo ảnh cloud cho {missing} cảnh thiếu ảnh
            </SecondaryButton>
          )}
        </div>
      )}

      <Section title={`Cảnh (${p.scenes.length})`}>
        <div className="grid gap-3">
          {p.scenes.map((s) => (
            <SceneCard key={s.id} scene={s} project={p} companyId={companyId} />
          ))}
        </div>
      </Section>

      <Section title="Sản xuất">
        <div className="flex flex-wrap gap-2 items-center">
          <Button disabled={busy || !p.image_source || produce.isPending} onClick={() => produce.mutate(false)}>
            {busy ? "Đang sản xuất…" : "Sản xuất video"}
          </Button>
          {missing > 0 && (
            <SecondaryButton disabled={busy || !p.image_source} onClick={() => produce.mutate(true)}>
              Thử với ảnh giữ chỗ cho {missing} cảnh thiếu
            </SecondaryButton>
          )}
        </div>
        <JobsSummary project={p} />
      </Section>

      {p.latest_render && <RenderResult project={p} />}
    </div>
  );
}

function ImageSourceChooser({ onChoose, pending }: { onChoose: (s: "manual" | "cloud") => void; pending: boolean }) {
  const [choice, setChoice] = useState<"manual" | "cloud">("manual");
  return (
    <div className="mb-4 p-3 rounded border border-indigo-700 bg-indigo-950/40" data-testid="image-source-chooser">
      <p className="text-sm font-medium mb-2">Chọn cách nhận ảnh cho video này</p>
      <label className="flex gap-2 text-sm mb-1">
        <input type="radio" checked={choice === "manual"} onChange={() => setChoice("manual")} />
        Nhập tay: tôi tự tải ảnh cho từng cảnh
      </label>
      <label className="flex gap-2 text-sm mb-2">
        <input type="radio" checked={choice === "cloud"} onChange={() => setChoice("cloud")} />
        AI cloud: tạo ảnh bằng dịch vụ đã cấu hình (vẫn tải ảnh tay được)
      </label>
      <Button disabled={pending} onClick={() => onChoose(choice)}>
        Xác nhận cách nhận ảnh
      </Button>
    </div>
  );
}

function SceneCard({ scene, project, companyId }: { scene: Scene; project: Project; companyId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [narration, setNarration] = useState(scene.narration);
  const setImage = useProjectAction(project.id, async (file: File) => {
    const asset = await uploadAsset(companyId, "image", file);
    return unwrap(
      await api.PUT("/api/v1/video-scenes/{scene_id}/image", {
        params: { path: { scene_id: scene.id } },
        body: { asset_id: asset.id },
      }),
    );
  });
  const save = useProjectAction(project.id, async () =>
    unwrap(
      await api.PATCH("/api/v1/video-scenes/{scene_id}", { params: { path: { scene_id: scene.id } }, body: { narration } }),
    ),
  );
  const gen = useProjectAction(project.id, () =>
    post(`/api/v1/video-projects/${project.id}/images`, { mode: "cloud", scene_ids: [scene.id], replace: true }),
  );
  const regen = useProjectAction(project.id, (segId: string) => post(`/api/v1/voice-segments/${segId}/regenerate`));
  const imgJob = project.jobs.find(
    (j) => j.kind === "image.generate" && j.payload_json.scene_id === scene.id && (j.status === "queued" || j.status === "running"),
  );
  const isPortrait = project.profile === "short";

  return (
    <div className="flex gap-3 p-3 rounded border border-slate-800 bg-slate-900/40" data-testid="scene-card">
      <div
        className={`shrink-0 ${isPortrait ? "w-28 h-48" : "w-48 h-28"} rounded border border-dashed border-slate-600 flex items-center justify-center overflow-hidden cursor-pointer`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) setImage.mutate(f);
        }}
        title="Bấm hoặc kéo thả ảnh vào đây"
      >
        {scene.image_asset_id ? (
          <img src={assetUrl(scene.image_asset_id)} alt={`Cảnh ${scene.index + 1}`} className="object-cover w-full h-full" />
        ) : (
          <span className="text-xs text-slate-500 text-center px-2">
            {imgJob ? "Đang tạo ảnh…" : "+ Thêm ảnh (PNG/JPG/WebP)"}
          </span>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          aria-label={`Ảnh cảnh ${scene.index + 1}`}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) setImage.mutate(f);
          }}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
          <span>Cảnh {scene.index + 1}</span>
          {scene.image_is_placeholder && <span className="text-amber-300">ảnh giữ chỗ</span>}
          {project.image_source === "cloud" && (
            <button className="underline" disabled={gen.isPending || !!imgJob} onClick={() => gen.mutate(undefined)}>
              {scene.image_asset_id ? "Tạo lại ảnh cloud" : "Tạo ảnh cloud"}
            </button>
          )}
        </div>
        <textarea
          className={`${inputClass} h-16`}
          value={narration}
          onChange={(e) => setNarration(e.target.value)}
          aria-label={`Lời đọc cảnh ${scene.index + 1}`}
        />
        {narration !== scene.narration && (
          <SecondaryButton className="mt-1" onClick={() => save.mutate(undefined)}>
            Lưu lời đọc (tạo lại giọng cảnh này)
          </SecondaryButton>
        )}
        {scene.visual_prompt && <p className="text-xs text-slate-500 mt-1">Gợi ý hình: {scene.visual_prompt}</p>}
        <ul className="mt-2 space-y-1">
          {scene.segments.map((g) => (
            <li key={g.id} className="text-xs flex flex-wrap items-center gap-2">
              <StatusBadge status={g.status} />
              <span className="text-slate-300 min-w-0 flex-1 truncate" title={g.normalized_text}>
                {g.normalized_text}
              </span>
              {g.asset_id && <audio controls preload="none" src={assetUrl(g.asset_id)} className="h-6 w-40 shrink-0" />}
              {g.duration_s != null && <span className="text-slate-500">{g.duration_s.toFixed(1)}s</span>}
              {g.asset_id && (
                <button className="underline text-slate-400" onClick={() => regen.mutate(g.id)}>
                  Đọc lại đoạn này
                </button>
              )}
              {g.error && <span className="text-red-300">{g.error}</span>}
            </li>
          ))}
        </ul>
        {(setImage.error || gen.error || regen.error || save.error) && (
          <p className="text-sm text-red-300 mt-1">{errorMessage(setImage.error ?? gen.error ?? regen.error ?? save.error)}</p>
        )}
      </div>
    </div>
  );
}

function JobsSummary({ project }: { project: Project }) {
  const active = project.jobs.filter((j) => j.status === "queued" || j.status === "running");
  if (!active.length) return null;
  const kinds: Record<string, string> = { "tts.segment": "giọng đọc", "image.generate": "ảnh", "video.render": "render", "video.asr_qa": "kiểm tra ASR" };
  return (
    <ul className="mt-2 text-xs text-slate-400 space-y-0.5" aria-label="Việc đang chạy">
      {active.slice(0, 8).map((j) => (
        <li key={j.id}>
          {kinds[j.kind] ?? j.kind}: {j.status === "running" ? `đang chạy ${Math.round(j.progress * 100)}%` : "đang chờ"}
          {j.progress_note && ` · ${j.progress_note}`}
        </li>
      ))}
      {active.length > 8 && <li>… và {active.length - 8} việc khác</li>}
    </ul>
  );
}

type Check = { id: string; ok: boolean; detail: string; severity: string };

function RenderResult({ project }: { project: Project }) {
  const r = project.latest_render!;
  const qa = (r.qa_json ?? {}) as { checks?: Check[]; passed?: boolean; asr?: { status: string; wer?: number; reason?: string } };
  return (
    <Section title={`Bản render v${r.version}`}>
      {r.status === "failed" && <p className="text-sm text-red-300">{r.error}</p>}
      {r.asset_id && (
        <div className="flex flex-wrap gap-4">
          <video
            controls
            src={assetUrl(r.asset_id)}
            className={project.profile === "short" ? "h-[480px] rounded" : "w-[640px] rounded"}
            data-testid="render-video"
          />
          <div className="text-sm min-w-64">
            <p className="mb-2">
              QA: {qa.passed ? <span className="text-emerald-300">đạt</span> : <span className="text-amber-300">chưa đạt</span>}
              {r.render_seconds != null && <span className="text-slate-400"> · render {r.render_seconds.toFixed(0)} giây ({r.encoder})</span>}
            </p>
            <ul className="space-y-0.5">
              {(qa.checks ?? []).map((c) => (
                <li key={c.id} className={c.ok ? "text-slate-300" : c.severity === "warning" ? "text-amber-300" : "text-red-300"}>
                  {c.ok ? "✓" : "✗"} {c.id}: {c.detail}
                </li>
              ))}
              {qa.asr && (
                <li className="text-slate-400">
                  ASR: {qa.asr.status === "done" ? `WER ${((qa.asr.wer ?? 0) * 100).toFixed(1)}%` : qa.asr.reason ?? qa.asr.status}
                </li>
              )}
            </ul>
            <div className="flex gap-3 mt-3">
              <a className="underline" href={assetUrl(r.asset_id, true)}>
                Tải MP4
              </a>
              {r.subtitle_asset_id && (
                <a className="underline" href={assetUrl(r.subtitle_asset_id, true)}>
                  Tải phụ đề ASS
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </Section>
  );
}
