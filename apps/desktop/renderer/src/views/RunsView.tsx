import type { Run, Task } from "@orchestra/contracts";
import { useState } from "react";
import { useAgents, useRuns, useScenarios, useStartScenario, useTasks } from "../api/hooks";
import { useCancelTask, useCreateTask, useRetryTask, useSummarizeTask } from "../api/hooks-p2";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge, inputClass } from "../components/ui";
import { useSelection } from "../state/selection";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function RunsView({ companyId }: { companyId: string }) {
  const scenarios = useScenarios();
  const start = useStartScenario(companyId);
  const tasks = useTasks(companyId);
  const runs = useRuns(companyId);
  const agents = useAgents(companyId);
  const [showForm, setShowForm] = useState(false);

  const agentName = (id: string | null) => agents.data?.find((a) => a.id === id)?.name ?? "chưa giao";
  const runsByTask = new Map<string, Run[]>();
  for (const r of [...(runs.data ?? [])].reverse()) if (r.task_id) runsByTask.set(r.task_id, [...(runsByTask.get(r.task_id) ?? []), r]);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Tasks & Runs</h1>
      <Section title="Chạy kịch bản mock">
        {scenarios.isLoading && <Loading />}
        <div className="flex gap-2 flex-wrap">
          {scenarios.data?.map((s) => (
            <SecondaryButton key={s.id} title={s.description} disabled={start.isPending} onClick={() => start.mutate(s.id)}>
              ▶ {s.name}
            </SecondaryButton>
          ))}
        </div>
        {start.isError && <ErrorView error={start.error} />}
        {start.isSuccess && <p className="text-xs text-slate-500 mt-2">Backend đã nhận lệnh. Theo dõi ở Activity Console.</p>}
      </Section>
      <Section
        title="Cây task"
        actions={
          <button className="text-xs underline" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Đóng" : "+ Tạo task"}
          </button>
        }
      >
        {showForm && <CreateTaskForm companyId={companyId} tasks={tasks.data ?? []} onDone={() => setShowForm(false)} />}
        {tasks.isLoading && <Loading />}
        {tasks.isError && <ErrorView error={tasks.error} onRetry={() => tasks.refetch()} />}
        {tasks.data?.length === 0 && <Empty>Chưa có task. Chạy một kịch bản hoặc tạo task.</Empty>}
        {tasks.data && <TaskTree companyId={companyId} tasks={tasks.data} runsByTask={runsByTask} agentName={agentName} />}
      </Section>
    </div>
  );
}

function CreateTaskForm({ companyId, tasks, onDone }: { companyId: string; tasks: Task[]; onDone: () => void }) {
  const agents = useAgents(companyId);
  const create = useCreateTask(companyId);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assignee, setAssignee] = useState("");
  const [deps, setDeps] = useState<string[]>([]);
  const [attempts, setAttempts] = useState(1);
  const roots = tasks.filter((t) => t.parent_task_id === null);
  const active = agents.data?.filter((a) => a.status === "active") ?? [];
  const roles = [...new Set(active.map((a) => a.role))];
  return (
    <form
      className="mb-4 p-4 rounded border border-slate-800 space-y-2 max-w-lg"
      onSubmit={(e) => {
        e.preventDefault();
        const [kind, value] = assignee.split(":", 2);
        create.mutate(
          {
            title,
            description,
            assigned_agent_id: kind === "agent" ? value : null,
            required_role: kind === "role" ? value : null,
            depends_on: deps,
            max_attempts: attempts,
          },
          { onSuccess: onDone },
        );
      }}
    >
      <input className={inputClass} placeholder="Tiêu đề task" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className={inputClass} rows={2} placeholder="Mô tả" value={description} onChange={(e) => setDescription(e.target.value)} />
      <select className={inputClass} value={assignee} onChange={(e) => setAssignee(e.target.value)} aria-label="Giao cho">
        <option value="">— Giao cho —</option>
        <optgroup label="Theo vai trò (agent active đầu tiên)">
          {roles.map((r) => (
            <option key={r} value={`role:${r}`}>
              {r}
            </option>
          ))}
        </optgroup>
        <optgroup label="Agent cụ thể">
          {active.map((a) => (
            <option key={a.id} value={`agent:${a.id}`}>
              {a.name}
            </option>
          ))}
        </optgroup>
      </select>
      {roots.length > 0 && (
        <label className="block text-xs text-slate-400">
          Chỉ chạy sau khi các task này hoàn thành:
          <select
            multiple
            className={`${inputClass} h-24`}
            value={deps}
            onChange={(e) => setDeps([...e.target.selectedOptions].map((o) => o.value))}
          >
            {roots.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title} ({t.status})
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="text-xs text-slate-400 flex items-center gap-2">
        Số lần thử tối đa (chỉ thử lại lỗi tạm thời)
        <input type="number" min={1} max={5} className="w-16 bg-slate-900 border border-slate-700 rounded px-2 py-1"
          value={attempts} onChange={(e) => setAttempts(Number(e.target.value) || 1)} />
      </label>
      <p className="text-xs text-slate-500">Task tự tạo chạy bằng kịch bản mock chung (không gọi AI).</p>
      <Button type="submit" disabled={create.isPending || !title.trim() || !assignee}>
        {create.isPending ? "Đang tạo…" : "Tạo task"}
      </Button>
      {create.isError && <ErrorView error={create.error} />}
    </form>
  );
}

type TreeProps = {
  companyId: string;
  tasks: Task[];
  runsByTask: Map<string, Run[]>;
  agentName: (id: string | null) => string;
};

function TaskTree(props: TreeProps) {
  const children = new Map<string | null, Task[]>();
  for (const t of props.tasks) {
    const k = t.parent_task_id ?? null;
    children.set(k, [...(children.get(k) ?? []), t]);
  }
  const roots = [...(children.get(null) ?? [])].reverse(); // newest first
  const title = (id: string) => props.tasks.find((t) => t.id === id)?.title ?? id.slice(0, 8);
  return (
    <div className="space-y-4">
      {roots.map((t) => (
        <Node key={t.id} task={t} depth={0} childMap={children} title={title} {...props} />
      ))}
    </div>
  );
}

function Node(props: TreeProps & { task: Task; depth: number; childMap: Map<string | null, Task[]>; title: (id: string) => string }) {
  const { select, selection } = useSelection();
  const cancel = useCancelTask(props.companyId);
  const retry = useRetryTask(props.companyId);
  const summarize = useSummarizeTask(props.companyId);
  const t = props.task;
  const runs = props.runsByTask.get(t.id) ?? [];
  const run = runs[runs.length - 1];
  const selected = selection?.kind === "run" && run && selection.id === run.id;
  const isRoot = t.parent_task_id === null;
  const dependsOn = t.depends_on ?? [];
  const blockedBy = t.blocked_by ?? [];
  const err = cancel.error ?? retry.error ?? summarize.error;
  return (
    <div>
      <div style={{ paddingLeft: props.depth * 20 }} className={`flex items-center gap-2 py-1 text-sm rounded hover:bg-slate-900 ${selected ? "bg-slate-900" : ""}`}>
        <button disabled={!run} onClick={() => run && select({ kind: "run", id: run.id })} className="flex items-center gap-3 text-left flex-1 min-w-0">
          <StatusBadge status={t.status} />
          <span className="truncate">{t.title}</span>
          <span className="text-xs text-slate-500 shrink-0">
            {t.required_role ?? ""} · {props.agentName(t.assigned_agent_id)}
            {runs.length > 1 && ` · ${runs.length} lần chạy`}
          </span>
          {run?.error_code && <span className="text-xs font-mono text-red-400 shrink-0">{run.error_code}</span>}
        </button>
        {dependsOn.length > 0 && t.status === "pending" && (
          <span className={`text-xs ${blockedBy.length ? "text-red-300" : "text-slate-400"}`} title={dependsOn.map(props.title).join(", ")}>
            {blockedBy.length ? `bị chặn bởi: ${blockedBy.map(props.title).join(", ")}` : `chờ: ${dependsOn.map(props.title).join(", ")}`}
          </span>
        )}
        {isRoot && !TERMINAL.has(t.status) && (
          <button className="text-xs underline text-slate-400" disabled={cancel.isPending} onClick={() => cancel.mutate(t.id)}>
            hủy
          </button>
        )}
        {isRoot && (t.status === "failed" || t.status === "cancelled") && (
          <button className="text-xs underline text-indigo-300" disabled={retry.isPending} onClick={() => retry.mutate(t.id)}>
            chạy lại
          </button>
        )}
        {isRoot && TERMINAL.has(t.status) && (
          <button
            className="text-xs underline text-slate-400"
            disabled={summarize.isPending || summarize.isSuccess}
            onClick={() => summarize.mutate(t.id)}
            title="Thư ký tạo tóm tắt tự động (không dùng AI) và lưu vào Tri thức"
          >
            {summarize.isSuccess ? "đã tóm tắt" : "tóm tắt"}
          </button>
        )}
      </div>
      {err && <div style={{ paddingLeft: props.depth * 20 }}><ErrorView error={err} /></div>}
      {(props.childMap.get(t.id) ?? []).map((c) => (
        <Node key={c.id} {...props} task={c} depth={props.depth + 1} />
      ))}
    </div>
  );
}
