import type { Approval } from "@orchestra/contracts";
import { useState } from "react";
import { useAgents } from "../api/hooks";
import { useApprovals, useDecideApproval } from "../api/hooks-p2";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge, formatTime, inputClass } from "../components/ui";
import { useSelection } from "../state/selection";

export function ApprovalsView({ companyId }: { companyId: string }) {
  const approvals = useApprovals(companyId);
  if (approvals.isLoading) return <Loading />;
  if (approvals.isError) return <ErrorView error={approvals.error} onRetry={() => approvals.refetch()} />;
  const pending = approvals.data!.filter((a) => a.status === "pending");
  const history = approvals.data!.filter((a) => a.status !== "pending");
  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold mb-1">Phê duyệt</h1>
      <p className="text-sm text-slate-400 mb-4">
        Hành động L3 (tác động ra bên ngoài) luôn chờ người duyệt. Quyết định gắn với đúng nội dung đang hiển thị (checksum); nội dung đổi thì phải duyệt lại.
      </p>
      <Section title={`Đang chờ (${pending.length})`}>
        {pending.length === 0 && <Empty>Không có yêu cầu nào đang chờ.</Empty>}
        <div className="space-y-3">
          {pending.map((a) => (
            <PendingCard key={a.id} companyId={companyId} approval={a} />
          ))}
        </div>
      </Section>
      <Section title="Lịch sử">
        {history.length === 0 && <p className="text-sm text-slate-500">Chưa có.</p>}
        {history.map((a) => (
          <div key={a.id} className="flex items-center gap-3 text-sm py-1 border-b border-slate-900">
            <StatusBadge status={a.status} />
            <span className="font-mono text-xs">{a.action_type}</span>
            <span className="text-xs text-slate-500">{formatTime(a.decided_at)}</span>
            {a.execution_status && (
              <span className={`text-xs ${a.execution_status === "succeeded" ? "text-emerald-400" : "text-red-400"}`}>
                thực thi: {a.execution_status}
              </span>
            )}
            {a.decision_note && <span className="text-xs text-slate-400 truncate">“{a.decision_note}”</span>}
          </div>
        ))}
      </Section>
    </div>
  );
}

function PendingCard({ companyId, approval: a }: { companyId: string; approval: Approval }) {
  const agents = useAgents(companyId);
  const decide = useDecideApproval(companyId);
  const { select } = useSelection();
  const [note, setNote] = useState("");
  const agent = agents.data?.find((x) => x.id === a.requested_by_agent_id);
  const params = (a.request_json as { params?: unknown }).params;
  return (
    <div className="p-4 rounded border border-amber-800 bg-amber-950/20 space-y-2 text-sm">
      <div className="flex items-center gap-2">
        <StatusBadge status={a.status} />
        <span className="font-mono">{a.action_type}</span>
        <span className="text-xs text-amber-300">L{a.required_level}</span>
        <span className="text-xs text-slate-400 ml-auto">{formatTime(a.created_at)}</span>
      </div>
      <div className="text-slate-300">
        Yêu cầu bởi <b>{agent?.name ?? "agent"}</b>
        {a.run_id && (
          <button className="ml-2 text-xs underline text-slate-400" onClick={() => select({ kind: "run", id: a.run_id! })}>
            xem run
          </button>
        )}
      </div>
      <pre className="p-2 bg-slate-900 rounded text-xs whitespace-pre-wrap">{JSON.stringify(params, null, 2)}</pre>
      <div className="text-xs text-slate-500 font-mono break-all">checksum {a.checksum}</div>
      <input className={inputClass} placeholder="Ghi chú (không bắt buộc)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex gap-2">
        <Button disabled={decide.isPending} onClick={() => decide.mutate({ id: a.id, decision: "approve", checksum: a.checksum, note })}>
          Duyệt và thực thi
        </Button>
        <SecondaryButton disabled={decide.isPending} onClick={() => decide.mutate({ id: a.id, decision: "reject", checksum: a.checksum, note })}>
          Từ chối
        </SecondaryButton>
      </div>
      {decide.isError && <ErrorView error={decide.error} />}
    </div>
  );
}
