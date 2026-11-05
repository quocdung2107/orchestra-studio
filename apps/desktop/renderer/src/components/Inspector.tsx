import { useState } from "react";
import {
  fetchArtifactText,
  useAgent,
  useAgentAction,
  useAgentVersions,
  useRun,
  useRunEvents,
  useRuntimes,
  type AgentAction,
} from "../api/hooks";
import { errorMessage } from "../api/client";
import { describeEvent } from "../live/eventLog";
import { useSelection, type Selection } from "../state/selection";
import { ErrorView, Loading, SecondaryButton, StatusBadge, formatTime } from "./ui";

export function Inspector({ companyId, selection }: { companyId: string | null; selection: Selection }) {
  const { select } = useSelection();
  if (!companyId || !selection) {
    return <aside className="w-80 border-l border-slate-800 p-4 text-sm text-slate-500">Chọn một agent hoặc run để xem chi tiết.</aside>;
  }
  return (
    <aside className="w-96 border-l border-slate-800 overflow-auto">
      <div className="flex justify-between items-center px-4 py-2 border-b border-slate-800 text-xs text-slate-400">
        <span>Inspector</span>
        <button onClick={() => select(null)} aria-label="Đóng inspector">
          ✕
        </button>
      </div>
      <div className="p-4">
        {selection.kind === "agent" ? (
          <AgentInspector companyId={companyId} agentId={selection.id} />
        ) : (
          <RunInspector companyId={companyId} runId={selection.id} />
        )}
      </div>
    </aside>
  );
}

const ACTIONS: Record<string, AgentAction[]> = {
  draft: ["activate", "archive"],
  active: ["deactivate", "archive"],
  inactive: ["activate", "archive"],
  archived: [],
};
const ACTION_LABEL: Record<AgentAction, string> = { activate: "Kích hoạt", deactivate: "Tạm dừng", archive: "Lưu trữ" };

function AgentInspector({ companyId, agentId }: { companyId: string; agentId: string }) {
  const agent = useAgent(agentId);
  const versions = useAgentVersions(agentId);
  const runtimes = useRuntimes();
  const action = useAgentAction(companyId, agentId);
  if (agent.isLoading) return <Loading />;
  if (agent.isError) return <ErrorView error={agent.error} />;
  const a = agent.data!;
  const rt = runtimes.data?.find((r) => r.runtime_id === a.current_version?.runtime.runtime_id);
  return (
    <div className="space-y-4 text-sm">
      <div>
        <div className="text-lg font-semibold">{a.name}</div>
        <div className="text-slate-400">{a.role}</div>
        <div className="mt-2">
          <StatusBadge status={a.status} />
        </div>
      </div>
      <div className="flex gap-2 flex-wrap">
        {ACTIONS[a.status].map((act) => (
          <SecondaryButton key={act} disabled={action.isPending} onClick={() => action.mutate(act)}>
            {ACTION_LABEL[act]}
          </SecondaryButton>
        ))}
      </div>
      {action.isError && <ErrorView error={action.error} />}
      {a.current_version && (
        <div>
          <div className="text-xs uppercase text-slate-500 mb-1">Phiên bản hiện tại v{a.current_version.version_number}</div>
          <p className="whitespace-pre-wrap text-slate-300">{a.current_version.definition.instructions || "(chưa có chỉ dẫn)"}</p>
          <p className="mt-2 text-slate-400">Runtime: {rt?.display_name ?? a.current_version.runtime.runtime_id}</p>
          {rt && (
            <p className="text-xs text-slate-500 mt-1">
              Hỗ trợ: {Object.entries(rt.capabilities).filter(([, v]) => v).map(([k]) => k.replace("supports_", "")).join(", ") || "—"}
            </p>
          )}
        </div>
      )}
      <div>
        <div className="text-xs uppercase text-slate-500 mb-1">Lịch sử phiên bản</div>
        {versions.isLoading && <Loading />}
        {versions.data?.map((v) => (
          <div key={v.id} className="text-xs text-slate-400">
            v{v.version_number} · {formatTime(v.created_at)} · {v.created_by}
          </div>
        ))}
      </div>
    </div>
  );
}

function RunInspector({ companyId, runId }: { companyId: string; runId: string }) {
  const run = useRun(runId);
  const events = useRunEvents(companyId, runId);
  const [preview, setPreview] = useState<{ name: string; text: string } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  if (run.isLoading) return <Loading />;
  if (run.isError) return <ErrorView error={run.error} />;
  const r = run.data!;
  return (
    <div className="space-y-4 text-sm">
      <div>
        <div className="text-xs text-slate-500">Run</div>
        <div className="font-semibold">{r.task?.title ?? "(không có task)"}</div>
        <div className="text-slate-400">
          {r.agent_name} · {r.agent_role} · runtime {r.runtime_id}
        </div>
        <div className="mt-2">
          <StatusBadge status={r.status} />
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Bắt đầu {formatTime(r.started_at)} · Kết thúc {formatTime(r.finished_at)}
        </div>
      </div>
      {r.result_summary && (
        <div className="p-2 rounded bg-emerald-950/40 border border-emerald-900">{r.result_summary}</div>
      )}
      {r.error_code && (
        <div className="p-2 rounded bg-red-950/40 border border-red-900" role="alert">
          <div className="font-mono text-xs text-red-300">{r.error_code}</div>
          <div>{r.error_summary}</div>
        </div>
      )}
      <div>
        <div className="text-xs uppercase text-slate-500 mb-1">Artifacts</div>
        {r.artifacts.length === 0 && <div className="text-slate-500">Không có.</div>}
        {r.artifacts.map((a) => (
          <button
            key={a.id}
            className="block w-full text-left hover:bg-slate-800 rounded px-1"
            onClick={async () => {
              setPreviewError(null);
              try {
                setPreview({ name: a.name, text: await fetchArtifactText(a.id) });
              } catch (e) {
                setPreviewError(errorMessage(e));
              }
            }}
          >
            📄 {a.name} <span className="text-xs text-slate-500">{a.size_bytes} B · {a.checksum.slice(0, 15)}…</span>
          </button>
        ))}
        {previewError && <p className="text-red-300 text-xs">{previewError}</p>}
        {preview && (
          <pre className="mt-2 p-2 bg-slate-900 rounded text-xs whitespace-pre-wrap">
            {/* rendered as text, never as HTML */}
            {preview.text}
          </pre>
        )}
      </div>
      <div>
        <div className="text-xs uppercase text-slate-500 mb-1">Sự kiện của run</div>
        {events.data?.items.map((e) => (
          <div key={e.sequence} className="text-xs py-0.5">
            <span className="text-slate-500">#{e.sequence}</span> <span className="text-indigo-300">{e.event_type}</span>{" "}
            {describeEvent(e)}
          </div>
        ))}
      </div>
    </div>
  );
}
