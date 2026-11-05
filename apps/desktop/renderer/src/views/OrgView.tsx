import type { Department, OrgGraph } from "@orchestra/contracts";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import {
  useArchiveDepartment,
  useCreateDepartment,
  useOrg,
  useSaveLayout,
  useUpdateAgent,
  useUpdateDepartment,
} from "../api/hooks-p1";
import { Button, ErrorView, Loading, SecondaryButton, inputClass } from "../components/ui";
import { useSelection } from "../state/selection";
import { NODE_W, autoLayout, departmentColors } from "./orgLayout";

type AgentData = { name: string; role: string; status: string; dept?: string; color?: string };

function AgentNode({ data, selected }: NodeProps<Node<AgentData>>) {
  return (
    <div
      style={{ width: NODE_W, borderLeftColor: data.color ?? "#475569" }}
      className={`rounded border border-slate-700 border-l-4 bg-slate-900 px-3 py-2 text-xs text-slate-100 ${
        selected ? "ring-2 ring-indigo-400" : ""
      } ${data.status !== "active" ? "opacity-60" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <div className="font-semibold text-sm truncate">{data.name}</div>
      <div className="text-slate-400 truncate">
        {data.role}
        {data.dept ? ` · ${data.dept}` : ""}
      </div>
      <div className="text-slate-500">{data.status}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

function buildNodes(graph: OrgGraph, prev: Node<AgentData>[]): Node<AgentData>[] {
  const auto = autoLayout(graph);
  const prevPos = new Map(prev.map((n) => [n.id, n.position]));
  const colors = departmentColors(graph);
  const deptName = new Map(graph.departments.map((d) => [d.id, d.name]));
  return graph.agents.map((a) => {
    const id = `agent:${a.id}`;
    return {
      id,
      type: "agent",
      position: prevPos.get(id) ?? graph.layout[id] ?? auto[id] ?? { x: 0, y: 0 },
      deletable: false,
      data: {
        name: a.name,
        role: a.role,
        status: a.status,
        dept: a.department_id ? deptName.get(a.department_id) : undefined,
        color: a.department_id ? colors[a.department_id] : undefined,
      },
    };
  });
}

function buildEdges(graph: OrgGraph): Edge[] {
  const ids = new Set(graph.agents.map((a) => a.id));
  return graph.agents
    .filter((a) => a.reports_to_agent_id && ids.has(a.reports_to_agent_id))
    .map((a) => ({
      id: `reports:${a.id}`,
      source: `agent:${a.reports_to_agent_id}`,
      target: `agent:${a.id}`,
      type: "smoothstep",
    }));
}

const agentId = (nodeId: string) => nodeId.replace(/^agent:/, "");

export function OrgView({ companyId }: { companyId: string }) {
  const org = useOrg(companyId);
  const updateAgent = useUpdateAgent(companyId);
  const saveLayout = useSaveLayout(companyId);
  const { select } = useSelection();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<AgentData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [error, setError] = useState<string | null>(null);

  // Backend is the source of truth: rebuild from every fresh graph (ADR-0011).
  useEffect(() => {
    if (!org.data) return;
    setNodes((prev) => buildNodes(org.data!, prev));
    setEdges(buildEdges(org.data));
  }, [org.data, setNodes, setEdges]);

  const fail = (e: unknown) => setError(errorMessage(e));

  const onConnect = (c: Connection) => {
    if (!c.source || !c.target) return;
    setError(null);
    // Edge direction: manager (source, bottom) -> report (target, top).
    updateAgent.mutate(
      { id: agentId(c.target), body: { reports_to_agent_id: agentId(c.source) } },
      { onError: fail },
    );
  };

  const onEdgesDelete = (deleted: Edge[]) => {
    setError(null);
    for (const e of deleted) {
      updateAgent.mutate({ id: agentId(e.target), body: { reports_to_agent_id: null } }, { onError: fail });
    }
  };

  if (org.isLoading) return <Loading />;
  if (org.isError) return <ErrorView error={org.error} onRetry={() => org.refetch()} />;

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-baseline justify-between mb-2">
        <h1 className="text-xl font-semibold">Sơ đồ tổ chức</h1>
        <p className="text-xs text-slate-500">
          Kéo từ chấm dưới của quản lý xuống chấm trên của nhân viên để đặt quan hệ báo cáo. Chọn cạnh rồi nhấn Delete để gỡ.
        </p>
      </div>
      {error && (
        <div role="alert" className="mb-2 p-2 text-sm rounded border border-red-800 bg-red-950/50 text-red-200">
          Backend từ chối: {error}
        </div>
      )}
      <div className="flex gap-4 flex-1 min-h-[480px]">
        <div className="flex-1 rounded border border-slate-800" data-testid="org-canvas">
          {org.data!.agents.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">Chưa có agent.</p>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onEdgesDelete={onEdgesDelete}
              onNodeClick={(_e, n) => select({ kind: "agent", id: agentId(n.id) })}
              onNodeDragStop={(_e, _n, dragged) =>
                saveLayout.mutate(Object.fromEntries(dragged.map((d) => [d.id, d.position])), { onError: fail })
              }
              colorMode="dark"
              fitView
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>
        <DepartmentPanel companyId={companyId} graph={org.data!} onError={fail} />
      </div>
    </div>
  );
}

function DepartmentPanel({ companyId, graph, onError }: { companyId: string; graph: OrgGraph; onError: (e: unknown) => void }) {
  const create = useCreateDepartment(companyId);
  const update = useUpdateDepartment(companyId);
  const archive = useArchiveDepartment(companyId);
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const colors = useMemo(() => departmentColors(graph), [graph]);
  const children = new Map<string | null, Department[]>();
  for (const d of graph.departments) {
    const k = d.parent_department_id ?? null;
    children.set(k, [...(children.get(k) ?? []), d]);
  }
  const counts = new Map<string, number>();
  for (const a of graph.agents) if (a.department_id) counts.set(a.department_id, (counts.get(a.department_id) ?? 0) + 1);

  const renderTree = (pid: string | null, depth: number): React.ReactNode =>
    (children.get(pid) ?? []).map((d) => (
      <div key={d.id}>
        <div className="flex items-center gap-2 py-1 text-sm" style={{ paddingLeft: depth * 14 }}>
          <span className="w-2 h-2 rounded-full" style={{ background: colors[d.id] }} />
          <span className="flex-1 truncate">{d.name}</span>
          <span className="text-xs text-slate-500">{counts.get(d.id) ?? 0}</span>
          <select
            aria-label={`Trần quyền ${d.name}`}
            className="bg-slate-900 border border-slate-700 rounded text-xs"
            value={d.max_tool_level ?? ""}
            onChange={(e) =>
              update.mutate(
                { id: d.id, body: { max_tool_level: e.target.value === "" ? null : Number(e.target.value) } },
                { onError },
              )
            }
          >
            <option value="">kế thừa</option>
            {[0, 1, 2, 3].map((l) => (
              <option key={l} value={l}>
                ≤ L{l}
              </option>
            ))}
          </select>
          <button className="text-xs text-slate-500 hover:text-red-300" title="Lưu trữ" onClick={() => archive.mutate(d.id, { onError })}>
            ✕
          </button>
        </div>
        {renderTree(d.id, depth + 1)}
      </div>
    ));

  return (
    <div className="w-72 shrink-0 space-y-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-1">Phòng ban</h2>
        {graph.departments.length === 0 && <p className="text-sm text-slate-500">Chưa có phòng ban.</p>}
        {renderTree(null, 0)}
        <p className="text-xs text-slate-500 mt-1">Cột phải: trần quyền tool. Phòng ban không thể vượt trần của company.</p>
      </div>
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name, parent_department_id: parent || null }, { onSuccess: () => setName(""), onError });
        }}
      >
        <input className={inputClass} placeholder="Tên phòng ban mới" value={name} onChange={(e) => setName(e.target.value)} />
        <select className={inputClass} value={parent} onChange={(e) => setParent(e.target.value)}>
          <option value="">— Cấp cao nhất —</option>
          {graph.departments.map((d) => (
            <option key={d.id} value={d.id}>
              Thuộc {d.name}
            </option>
          ))}
        </select>
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          Tạo phòng ban
        </Button>
      </form>
      <SecondaryButton
        onClick={() =>
          (document.querySelector("[data-testid=org-canvas] .react-flow__controls-fitview") as HTMLButtonElement | null)?.click()
        }
      >
        Căn giữa sơ đồ
      </SecondaryButton>
    </div>
  );
}
