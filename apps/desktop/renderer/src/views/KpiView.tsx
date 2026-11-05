import type { KpiFigures } from "@orchestra/contracts";
import { useState } from "react";
import { useKpis } from "../api/hooks-p4";
import { ErrorView, Loading, Section, formatTime, inputClass } from "../components/ui";
import { useSelection } from "../state/selection";

export function pct(x: number | null | undefined): string {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

export function duration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${(ms / 60_000).toFixed(1)} phút`;
}

export function costLabel(k: Pick<KpiFigures, "cost_usd" | "llm_runs" | "unpriced_runs">): string {
  if (k.llm_runs === 0) return "—";
  const base = `~${k.cost_usd.toFixed(4)} USD`;
  return k.unpriced_runs > 0 ? `${base} (+${k.unpriced_runs} run chưa có giá)` : base;
}

const fmt = (n: number) => n.toLocaleString("vi-VN");

export function KpiView({ companyId }: { companyId: string }) {
  const [days, setDays] = useState(30);
  const kpis = useKpis(companyId, days);
  const { select } = useSelection();
  if (kpis.isLoading) return <Loading />;
  if (kpis.isError) return <ErrorView error={kpis.error} onRetry={() => kpis.refetch()} />;
  const k = kpis.data!;
  const t = k.totals;
  const cards: { label: string; value: string; src: keyof typeof k.sources }[] = [
    { label: "Run", value: `${t.runs} (${t.active} đang chạy)`, src: "runs" },
    { label: "Tỉ lệ thành công", value: `${pct(t.success_rate)} · ${t.completed}✓ ${t.failed}✗ ${t.cancelled}⊘`, src: "runs" },
    { label: "Lần chạy lại", value: String(t.retries), src: "runs" },
    { label: "Thời gian TB", value: duration(t.avg_duration_ms), src: "duration" },
    { label: "Token vào / ra", value: `${fmt(t.tokens_input)} / ${fmt(t.tokens_output)}`, src: "tokens" },
    { label: "Chi phí API", value: costLabel(t), src: "cost" },
  ];
  return (
    <div className="max-w-5xl">
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-xl font-semibold">Hiệu suất (KPI)</h1>
        <select className={`${inputClass} max-w-[10rem]`} aria-label="Khoảng thời gian" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[1, 7, 30, 90].map((d) => (
            <option key={d} value={d}>
              {d} ngày qua
            </option>
          ))}
        </select>
      </div>
      <p className="text-sm text-slate-400 mb-4">Mỗi con số ghi rõ nguồn và độ tin cậy. Chi phí là ước tính, không phải hóa đơn.</p>

      <div className="grid gap-3 grid-cols-2 md:grid-cols-3 mb-6">
        {cards.map((c) => (
          <div key={c.label} className="p-3 rounded border border-slate-800">
            <div className="text-xs text-slate-500">{c.label}</div>
            <div className="text-lg font-semibold">{c.value}</div>
            <div className="text-[11px] text-slate-500" title={k.sources[c.src]?.note}>
              {k.sources[c.src]?.confidence} · {k.sources[c.src]?.source}
            </div>
          </div>
        ))}
      </div>

      <Section title="Theo agent">
        <KpiTable
          rows={k.by_agent.map((a) => ({ key: a.agent_id, name: `${a.agent_name} · ${a.role}`, onClick: () => select({ kind: "agent", id: a.agent_id }), ...a }))}
        />
      </Section>
      <Section title="Theo runtime">
        <KpiTable rows={k.by_runtime.map((r) => ({ key: r.runtime_id, name: r.runtime_id, ...r }))} />
      </Section>

      <Section title="Nguồn số liệu">
        <ul className="text-xs text-slate-400 space-y-1">
          {Object.entries(k.sources).map(([name, s]) => (
            <li key={name}>
              <b className="text-slate-300">{name}</b>: {s.note} — nguồn <code>{s.source}</code>, độ tin cậy <code>{s.confidence}</code>
            </li>
          ))}
          <li>
            Bảng giá ngày {k.price_table.as_of as string}: {k.price_table.source as string}. Model không có trong bảng thì không tính chi phí.
          </li>
          <li>Ollama: không có phí API; không tính điện và phần cứng.</li>
          <li>Tạo lúc {formatTime(k.generated_at)}.</li>
        </ul>
      </Section>
    </div>
  );
}

type Row = KpiFigures & { key: string; name: string; onClick?: () => void };

function KpiTable({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">Chưa có run trong khoảng này.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-slate-500 text-left">
        <tr>
          <th className="py-1">Tên</th>
          <th>Run</th>
          <th>Thành công</th>
          <th>Retry</th>
          <th>TB</th>
          <th>Token vào/ra</th>
          <th>Chi phí (ước tính)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key} className="border-t border-slate-900">
            <td className="py-1">
              {r.onClick ? (
                <button className="underline decoration-dotted" onClick={r.onClick}>
                  {r.name}
                </button>
              ) : (
                <span className="font-mono">{r.name}</span>
              )}
            </td>
            <td>{r.runs}</td>
            <td>{pct(r.success_rate)}</td>
            <td>{r.retries}</td>
            <td>{duration(r.avg_duration_ms)}</td>
            <td>
              {fmt(r.tokens_input)} / {fmt(r.tokens_output)}
            </td>
            <td>{costLabel(r)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
