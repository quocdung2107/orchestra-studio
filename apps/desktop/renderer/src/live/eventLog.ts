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
  const pl = e.payload as { agent_id?: string; skill_id?: string };
  if (t.startsWith("company.")) out.push(["companies"], ["company", cid], ["toolAccess"]);
  if (t.startsWith("department.")) out.push(["org", cid], ["departments", cid], ["toolAccess"]);
  if (t.startsWith("agent.") && !t.startsWith("agent.run.")) {
    out.push(["agents", cid], ["org", cid]);
    if (pl.agent_id) out.push(["agent", pl.agent_id], ["versions", pl.agent_id]);
    if (t.startsWith("agent.skill_") && pl.agent_id) out.push(["agentSkills", pl.agent_id]);
    if (t.startsWith("agent.tool_") && pl.agent_id) out.push(["toolAccess", pl.agent_id]);
  }
  if (t.startsWith("skill.")) {
    out.push(["skills", cid], ["agentSkills"]);
    if (pl.skill_id) out.push(["skillVersions", pl.skill_id]);
  }
  if (t === "tool.created" || t === "tool.updated" || t === "tool.archived") out.push(["tools", cid], ["toolAccess"]);
  if (t.startsWith("approval.")) out.push(["approvals", cid]);
  if (t.startsWith("knowledge.")) out.push(["knowledge", cid]);
  if (t.startsWith("lesson.")) out.push(["lessons", cid]);
  if (t.startsWith("role_change.")) out.push(["roleProposals", cid]);
  if (t.startsWith("task.")) out.push(["tasks", cid]);
  if (t.startsWith("credential.")) out.push(["credentials"]);
  if (t === "agent.run.usage_recorded" || t === "agent.run.completed" || t === "agent.run.failed")
    out.push(["kpis", cid]);
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
    case "department.created":
      return `Tạo phòng ban "${p.name}"`;
    case "agent.updated":
    case "department.updated":
    case "company.updated":
      return `Thay đổi: ${Object.keys((p.changes as object) ?? {}).join(", ")}`;
    case "skill.created":
      return `Tạo skill "${p.name}"`;
    case "skill.version_created":
    case "agent.version_created":
      return `Phiên bản mới v${p.version_number}`;
    case "agent.skill_attached":
      return `Gắn skill (v${p.version_number})`;
    case "tool.created":
    case "tool.updated":
      return `Tool ${p.key} v${p.version}`;
    case "agent.tool_granted":
      return `Cấp tool (L${p.permission_level})`;
    case "template.instantiated":
      return `Tạo từ template ${p.template_id}`;
    case "agent.run.status_changed":
      return `Run: ${p.from_status} → ${p.to_status}`;
    case "agent.run.cancelled":
      return "Run đã hủy";
    case "agent.run.retry_scheduled":
      return `Thử lại lần ${p.next_attempt} sau ${p.delay_ms} ms`;
    case "task.dependency_added":
      return "Thêm phụ thuộc";
    case "task.retry_requested":
      return "Yêu cầu chạy lại";
    case "task.cancel_requested":
      return "Yêu cầu hủy";
    case "tool.call_requested":
      return `Gọi tool ${p.tool_key} (L${p.permission_level})`;
    case "tool.call_denied":
      return `Từ chối tool ${p.tool_key}: ${p.error_code} (${p.reason})`;
    case "tool.call_finished":
      return `Tool ${p.tool_key}: ${p.ok ? "thành công" : `lỗi ${p.error_code}`}`;
    case "approval.requested":
      return `Cần phê duyệt: ${p.action_type}`;
    case "approval.decided":
    case "approval.closed":
      return `Phê duyệt: ${p.status}`;
    case "knowledge.created":
    case "knowledge.updated":
      return `Tri thức "${p.title}" v${p.version} (${p.source_type})`;
    case "lesson.proposed":
      return `Đề xuất bài học "${p.title}"`;
    case "lesson.reviewed":
    case "role_change.reviewed":
      return `Đã duyệt: ${p.status}`;
    case "role_change.proposed":
      return `Đề xuất đổi vai trò: ${Object.keys((p.changes as object) ?? {}).join(", ")}`;
    case "agent.run.usage_recorded": {
      const cost =
        typeof p.cost_usd === "number" ? ` · ~${(p.cost_usd as number).toFixed(4)} USD (ước tính)` : " · chưa có giá";
      return `${p.model}: ${p.input_tokens} token vào, ${p.output_tokens} token ra${cost}`;
    }
    case "credential.created":
      return `Thêm credential "${p.label}" (${p.provider})`;
    case "credential.rotated":
      return `Xoay secret của "${p.label}"`;
    case "credential.revoked":
      return `Thu hồi credential "${p.label}"`;
    case "credential.verified":
      return `Kiểm tra "${p.label}": ${p.ok ? "OK" : "lỗi"}`;
    case "scenario.started":
      return `Bắt đầu kịch bản ${p.scenario_id}`;
    default:
      return "";
  }
}
