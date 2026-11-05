import { useAgents, useCompany, useRuns, useTasks } from "../api/hooks";
import { useUpdateCompany } from "../api/hooks-p1";
import { ErrorView, Loading, Section, StatusBadge } from "../components/ui";
import { useSelection } from "../state/selection";

export function CompanyOverview({ companyId }: { companyId: string }) {
  const company = useCompany(companyId);
  const agents = useAgents(companyId);
  const tasks = useTasks(companyId);
  const runs = useRuns(companyId);
  const { select, setView } = useSelection();
  if (company.isLoading) return <Loading />;
  if (company.isError) return <ErrorView error={company.error} />;
  const c = company.data!;
  const count = (xs: { status: string }[] | undefined, s: string) => xs?.filter((x) => x.status === s).length ?? 0;
  const stats = [
    { label: "Agent đang hoạt động", value: count(agents.data, "active"), total: agents.data?.length },
    { label: "Task đang chạy", value: count(tasks.data, "in_progress"), total: tasks.data?.length },
    { label: "Run thất bại", value: count(runs.data, "failed"), total: runs.data?.length },
  ];
  return (
    <div>
      <h1 className="text-2xl font-semibold">{c.name}</h1>
      <p className="text-slate-400 mb-2">{c.description || "—"}</p>
      <CeilingSetting companyId={companyId} level={c.max_tool_level} />
      <ParallelSetting companyId={companyId} value={c.max_parallel_runs} />
      <div className="grid grid-cols-3 gap-4 mb-8">
        {stats.map((s) => (
          <div key={s.label} className="p-4 rounded border border-slate-800 bg-slate-900/40">
            <div className="text-xs text-slate-400">{s.label}</div>
            <div className="text-2xl font-semibold">
              {s.value}
              <span className="text-sm text-slate-500"> / {s.total ?? "…"}</span>
            </div>
          </div>
        ))}
      </div>
      <Section title="Run gần đây" actions={<button className="text-xs underline" onClick={() => setView("runs")}>Xem tất cả</button>}>
        {runs.isError && <ErrorView error={runs.error} />}
        {runs.data?.length === 0 && <p className="text-sm text-slate-500">Chưa có run nào.</p>}
        {runs.data?.slice(0, 5).map((r) => (
          <button key={r.id} onClick={() => select({ kind: "run", id: r.id })} className="flex gap-3 items-center text-sm py-1 hover:underline">
            <StatusBadge status={r.status} />
            <span>{r.result_summary ?? r.error_summary ?? r.id.slice(0, 8)}</span>
          </button>
        ))}
      </Section>
    </div>
  );
}

const LEVELS = ["L0 · chỉ đọc", "L1 · tạo nháp", "L2 · ghi trong workspace", "L3 · tác động bên ngoài (cần duyệt)"];

function CeilingSetting({ companyId, level }: { companyId: string; level: number }) {
  const update = useUpdateCompany(companyId);
  return (
    <div className="mb-6 text-sm flex items-center gap-2">
      <span className="text-slate-400">Trần quyền tool của company:</span>
      <select
        className="bg-slate-900 border border-slate-700 rounded px-2 py-1"
        value={level}
        disabled={update.isPending}
        onChange={(e) => update.mutate({ max_tool_level: Number(e.target.value) })}
      >
        {LEVELS.map((l, i) => (
          <option key={i} value={i}>
            {l}
          </option>
        ))}
      </select>
      {update.isError && <ErrorView error={update.error} />}
    </div>
  );
}

function ParallelSetting({ companyId, value }: { companyId: string; value: number }) {
  const update = useUpdateCompany(companyId);
  return (
    <div className="mb-6 -mt-4 text-sm flex items-center gap-2">
      <span className="text-slate-400">Số task gốc chạy song song tối đa:</span>
      <select
        className="bg-slate-900 border border-slate-700 rounded px-2 py-1"
        value={value}
        disabled={update.isPending}
        onChange={(e) => update.mutate({ max_parallel_runs: Number(e.target.value) })}
      >
        {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      {update.isError && <ErrorView error={update.error} />}
    </div>
  );
}
