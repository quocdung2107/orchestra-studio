import { useApprovals } from "../api/hooks-p2";
import type { Company } from "@orchestra/contracts";
import { useSelection, type View } from "../state/selection";

const NAV: { view: View; label: string; phase?: string }[] = [
  { view: "overview", label: "Tổng quan" },
  { view: "agents", label: "Agents" },
  { view: "runs", label: "Tasks & Runs" },
  { view: "organization", label: "Sơ đồ tổ chức" },
  { view: "capabilities", label: "Skills & Tools" },
  { view: "approvals", label: "Phê duyệt" },
  { view: "knowledge", label: "Tri thức" },
  { view: "analytics", label: "Hiệu suất (KPI)" },
  { view: "connections", label: "Kết nối & model" },
];

export function Sidebar({ companies }: { companies: Company[] }) {
  const { companyId, setCompanyId, view, setView } = useSelection();
  return (
    <aside className="row-span-1 border-r border-slate-800 bg-slate-900/60 flex flex-col">
      <div className="p-4 border-b border-slate-800">
        <div className="text-base font-semibold">Orchestra Studio</div>
        <label className="block mt-3 text-xs text-slate-400" htmlFor="company-select">
          Company
        </label>
        <select
          id="company-select"
          className="mt-1 w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
          value={companyId ?? ""}
          onChange={(e) => setCompanyId(e.target.value || null)}
        >
          <option value="">— Chọn company —</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <nav className="p-2 flex-1">
        {NAV.map((n) => (
          <button
            key={n.view}
            disabled={!companyId}
            onClick={() => setView(n.view)}
            className={`w-full text-left px-3 py-1.5 rounded text-sm flex justify-between disabled:opacity-40 ${
              view === n.view ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800/60"
            }`}
          >
            <span>{n.label}</span>
            {n.phase && <span className="text-xs text-slate-500">{n.phase}</span>}
            {n.view === "approvals" && companyId && <PendingBadge companyId={companyId} />}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function PendingBadge({ companyId }: { companyId: string }) {
  const approvals = useApprovals(companyId);
  const n = approvals.data?.filter((a) => a.status === "pending").length ?? 0;
  if (!n) return null;
  return <span className="text-xs px-1.5 rounded bg-amber-600 text-white" aria-label={`${n} yêu cầu chờ duyệt`}>{n}</span>;
}
