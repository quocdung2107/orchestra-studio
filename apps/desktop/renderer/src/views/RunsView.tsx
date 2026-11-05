import type { Run, Task } from "@orchestra/contracts";
import { useAgents, useRuns, useScenarios, useStartScenario, useTasks } from "../api/hooks";
import { Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge } from "../components/ui";
import { useSelection } from "../state/selection";

export function RunsView({ companyId }: { companyId: string }) {
  const scenarios = useScenarios();
  const start = useStartScenario(companyId);
  const tasks = useTasks(companyId);
  const runs = useRuns(companyId);
  const agents = useAgents(companyId);
  const busy = tasks.data?.some((t) => t.status === "in_progress") ?? false;

  const agentName = (id: string | null) => agents.data?.find((a) => a.id === id)?.name ?? "chưa giao";
  const latestRun = new Map<string, Run>();
  for (const r of [...(runs.data ?? [])].reverse()) if (r.task_id) latestRun.set(r.task_id, r);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Tasks & Runs</h1>
      <Section title="Chạy kịch bản mock">
        {scenarios.isLoading && <Loading />}
        <div className="flex gap-2 flex-wrap">
          {scenarios.data?.map((s) => (
            <SecondaryButton key={s.id} title={s.description} disabled={start.isPending || busy} onClick={() => start.mutate(s.id)}>
              ▶ {s.name}
            </SecondaryButton>
          ))}
        </div>
        {busy && <p className="text-xs text-slate-500 mt-2">Đang có task chạy; P0 chạy tuần tự từng kịch bản một.</p>}
        {start.isError && <ErrorView error={start.error} />}
        {start.isSuccess && !busy && <p className="text-xs text-slate-500 mt-2">Backend đã nhận lệnh. Theo dõi ở Activity Console.</p>}
      </Section>
      <Section title="Cây task">
        {tasks.isLoading && <Loading />}
        {tasks.isError && <ErrorView error={tasks.error} onRetry={() => tasks.refetch()} />}
        {tasks.data?.length === 0 && <Empty>Chưa có task. Chạy một kịch bản để bắt đầu.</Empty>}
        {tasks.data && <TaskTree tasks={tasks.data} latestRun={latestRun} agentName={agentName} />}
      </Section>
    </div>
  );
}

function TaskTree(props: { tasks: Task[]; latestRun: Map<string, Run>; agentName: (id: string | null) => string }) {
  const children = new Map<string | null, Task[]>();
  for (const t of props.tasks) {
    const k = t.parent_task_id ?? null;
    children.set(k, [...(children.get(k) ?? []), t]);
  }
  const roots = [...(children.get(null) ?? [])].reverse(); // newest scenario first
  return (
    <div className="space-y-4">
      {roots.map((t) => (
        <Node key={t.id} task={t} depth={0} children={children} {...props} />
      ))}
    </div>
  );
}

function Node(props: {
  task: Task;
  depth: number;
  children: Map<string | null, Task[]>;
  latestRun: Map<string, Run>;
  agentName: (id: string | null) => string;
}) {
  const { select, selection } = useSelection();
  const run = props.latestRun.get(props.task.id);
  const selected = selection?.kind === "run" && run && selection.id === run.id;
  return (
    <div>
      <button
        disabled={!run}
        onClick={() => run && select({ kind: "run", id: run.id })}
        style={{ paddingLeft: props.depth * 20 }}
        className={`w-full text-left flex items-center gap-3 py-1 text-sm rounded hover:bg-slate-900 ${selected ? "bg-slate-900" : ""}`}
      >
        <StatusBadge status={props.task.status} />
        <span>{props.task.title}</span>
        <span className="text-xs text-slate-500">
          {props.task.required_role} · {props.agentName(props.task.assigned_agent_id)}
        </span>
        {run?.error_code && <span className="text-xs font-mono text-red-400">{run.error_code}</span>}
      </button>
      {(props.children.get(props.task.id) ?? []).map((c) => (
        <Node key={c.id} {...props} task={c} depth={props.depth + 1} />
      ))}
    </div>
  );
}
