import type { EventEnvelope } from "@orchestra/contracts";

export const MAX_EVENTS = 1000;

/** Merge events by sequence: idempotent on duplicates, ordered, bounded. */
export function mergeEvents(current: EventEnvelope[], incoming: EventEnvelope[]): EventEnvelope[] {
  if (incoming.length === 0) return current;
  const bySeq = new Map<number, EventEnvelope>();
  for (const e of current) bySeq.set(e.sequence, e);
  let changed = false;
  for (const e of incoming) {
    if (!bySeq.has(e.sequence)) {
      bySeq.set(e.sequence, e);
      changed = true;
    }
  }
  if (!changed) return current;
  const merged = [...bySeq.values()].sort((a, b) => a.sequence - b.sequence);
  return merged.length > MAX_EVENTS ? merged.slice(merged.length - MAX_EVENTS) : merged;
}

/** Which cached queries an event makes stale. */
export function queriesToRefresh(e: EventEnvelope): string[][] {
  const cid = e.company_id;
  const out: string[][] = [];
  const t = e.event_type;
  if (t.startsWith("company.")) out.push(["companies"], ["company", cid]);
  if (t.startsWith("agent.") && !t.startsWith("agent.run.")) {
    out.push(["agents", cid]);
    const agentId = (e.payload as { agent_id?: string }).agent_id;
    if (agentId) out.push(["agent", agentId], ["versions", agentId]);
  }
  if (t.startsWith("task.")) out.push(["tasks", cid]);
  if (t.startsWith("agent.run.") || t === "artifact.created") {
    out.push(["runs", cid]);
    if (e.run_id) out.push(["run", e.run_id], ["runEvents", e.run_id]);
  }
  return out;
}

export function describeEvent(e: EventEnvelope): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "company.created":
      return `Tạo company "${p.name}"`;
    case "agent.created":
      return `Tạo agent ${p.name} (${p.role})`;
    case "task.created":
      return `Tạo task "${p.title}"`;
    case "task.status_changed":
      return `Task: ${p.from_status} → ${p.to_status}`;
    case "agent.run.progress":
      return String(p.message);
    case "agent.run.message":
      return String(p.text);
    case "agent.run.delegated":
      return `Giao việc cho ${p.to_role}`;
    case "agent.run.completed":
      return `Hoàn thành: ${p.summary}`;
    case "agent.run.failed":
      return `Lỗi ${p.error_code}: ${p.error_summary}`;
    case "artifact.created":
      return `Artifact ${p.name} (${p.size_bytes} bytes)`;
    case "scenario.started":
      return `Bắt đầu kịch bản ${p.scenario_id}`;
    default:
      return "";
  }
}
