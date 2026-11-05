import type { OrgGraph } from "@orchestra/contracts";

export const NODE_W = 200;
export const NODE_H = 70;

/** Tree layout by reporting depth, used only when no saved position exists. */
export function autoLayout(graph: OrgGraph): Record<string, { x: number; y: number }> {
  const byId = new Map(graph.agents.map((a) => [a.id, a]));
  const depthCache = new Map<string, number>();
  const depth = (id: string, guard = 0): number => {
    if (depthCache.has(id)) return depthCache.get(id)!;
    const a = byId.get(id);
    const parent = a?.reports_to_agent_id;
    const d = parent && byId.has(parent) && guard < 50 ? depth(parent, guard + 1) + 1 : 0;
    depthCache.set(id, d);
    return d;
  };
  const rows = new Map<number, string[]>();
  for (const a of graph.agents) {
    const d = depth(a.id);
    rows.set(d, [...(rows.get(d) ?? []), a.id]);
  }
  const out: Record<string, { x: number; y: number }> = {};
  for (const [d, ids] of rows) {
    ids.forEach((id, i) => {
      out[`agent:${id}`] = { x: i * (NODE_W + 40) - ((ids.length - 1) * (NODE_W + 40)) / 2, y: d * (NODE_H + 80) };
    });
  }
  return out;
}

const PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316"];

export function departmentColors(graph: OrgGraph): Record<string, string> {
  const out: Record<string, string> = {};
  graph.departments.forEach((d, i) => (out[d.id] = PALETTE[i % PALETTE.length]));
  return out;
}
