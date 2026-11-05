import { useState } from "react";
import { useAgents, useCreateAgent, useRuntimes } from "../api/hooks";
import { Button, Empty, ErrorView, Loading, Section, StatusBadge, inputClass } from "../components/ui";
import { useSelection } from "../state/selection";

export function AgentsView({ companyId }: { companyId: string }) {
  const agents = useAgents(companyId);
  const { select, selection } = useSelection();
  const [showForm, setShowForm] = useState(false);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Agents</h1>
      <Section title="Danh sách" actions={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Đóng" : "Tạo agent"}</Button>}>
        {showForm && <CreateAgentForm companyId={companyId} onDone={() => setShowForm(false)} />}
        {agents.isLoading && <Loading />}
        {agents.isError && <ErrorView error={agents.error} onRetry={() => agents.refetch()} />}
        {agents.data?.length === 0 && <Empty>Chưa có agent. Tạo agent đầu tiên.</Empty>}
        {!!agents.data?.length && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="py-1">Tên</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {agents.data.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => select({ kind: "agent", id: a.id })}
                  className={`cursor-pointer border-t border-slate-800 hover:bg-slate-900 ${
                    selection?.kind === "agent" && selection.id === a.id ? "bg-slate-900" : ""
                  }`}
                >
                  <td className="py-1.5">{a.name}</td>
                  <td>{a.role}</td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  );
}

function CreateAgentForm({ companyId, onDone }: { companyId: string; onDone: () => void }) {
  const create = useCreateAgent(companyId);
  const runtimes = useRuntimes();
  const { select } = useSelection();
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [instructions, setInstructions] = useState("");
  const [runtimeId, setRuntimeId] = useState("mock");

  return (
    <form
      className="mb-6 p-4 rounded border border-slate-800 space-y-2 max-w-lg"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(
          { name, role, definition: { instructions }, runtime: { runtime_id: runtimeId } },
          { onSuccess: (a) => { select({ kind: "agent", id: a.id }); onDone(); } },
        );
      }}
    >
      <input className={inputClass} placeholder="Tên" value={name} onChange={(e) => setName(e.target.value)} />
      <input className={inputClass} placeholder="Vai trò (ví dụ Researcher)" value={role} onChange={(e) => setRole(e.target.value)} />
      <textarea className={inputClass} rows={3} placeholder="Chỉ dẫn" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
      <select className={inputClass} value={runtimeId} onChange={(e) => setRuntimeId(e.target.value)}>
        {runtimes.data?.map((r) => (
          <option key={r.runtime_id} value={r.runtime_id}>
            {r.display_name}
          </option>
        ))}
      </select>
      <Button type="submit" disabled={create.isPending || !name.trim() || !role.trim()}>
        {create.isPending ? "Đang tạo…" : "Tạo (trạng thái draft)"}
      </Button>
      {create.isError && <ErrorView error={create.error} />}
    </form>
  );
}
