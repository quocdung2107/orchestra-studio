import type { EventEnvelope } from "@orchestra/contracts";
import { describe, expect, it } from "vitest";
import { MAX_EVENTS, describeEvent, mergeEvents, queriesToRefresh } from "./eventLog";

const ev = (sequence: number, event_type = "agent.run.progress", extra: Partial<EventEnvelope> = {}): EventEnvelope => ({
  id: `id-${sequence}`,
  company_id: "c1",
  run_id: "r1",
  sequence,
  event_type,
  schema_version: 1,
  occurred_at: "2026-11-05T12:00:00Z",
  source: "runtime.mock",
  correlation_id: null,
  causation_id: null,
  idempotency_key: null,
  payload: { run_id: "r1", message: `step ${sequence}` },
  ...extra,
});

describe("mergeEvents", () => {
  it("orders by sequence and ignores duplicates (reconnect replay)", () => {
    const a = mergeEvents([], [ev(2), ev(1)]);
    const b = mergeEvents(a, [ev(2), ev(3)]);
    expect(b.map((e) => e.sequence)).toEqual([1, 2, 3]);
  });

  it("returns the same array when nothing new arrives", () => {
    const a = mergeEvents([], [ev(1)]);
    expect(mergeEvents(a, [ev(1)])).toBe(a);
  });

  it("keeps only the newest MAX_EVENTS", () => {
    const many = Array.from({ length: MAX_EVENTS + 5 }, (_, i) => ev(i + 1));
    const out = mergeEvents([], many);
    expect(out).toHaveLength(MAX_EVENTS);
    expect(out[0].sequence).toBe(6);
  });
});

describe("queriesToRefresh", () => {
  it("refreshes runs and the specific run for run events", () => {
    expect(queriesToRefresh(ev(1, "agent.run.completed"))).toEqual([["kpis", "c1"], ["runs", "c1"], ["run", "r1"], ["runEvents", "r1"]]);
  });
  it("refreshes agent caches for agent events but not run events", () => {
    const keys = queriesToRefresh(ev(1, "agent.activated", { run_id: null, payload: { agent_id: "a1" } }));
    expect(keys).toContainEqual(["agents", "c1"]);
    expect(keys).toContainEqual(["agent", "a1"]);
  });
});

describe("describeEvent", () => {
  it("formats failures with their code", () => {
    const e = ev(1, "agent.run.failed", { payload: { run_id: "r1", error_code: "X", error_summary: "boom" } });
    expect(describeEvent(e)).toBe("Lỗi X: boom");
  });
});

describe("P2/P3 events", () => {
  it("refreshes approvals, knowledge, lessons and proposals", () => {
    const keys = (t: string) => queriesToRefresh(ev(1, t)).map((k) => k[0]);
    expect(keys("approval.requested")).toContain("approvals");
    expect(keys("knowledge.created")).toContain("knowledge");
    expect(keys("lesson.proposed")).toContain("lessons");
    expect(keys("role_change.reviewed")).toContain("roleProposals");
  });
  it("does not refetch the tool catalog for every tool call", () => {
    expect(queriesToRefresh(ev(1, "tool.call_finished")).map((k) => k[0])).not.toContain("tools");
    expect(queriesToRefresh(ev(1, "tool.updated")).map((k) => k[0])).toContain("tools");
  });
  it("describes approvals and tool calls", () => {
    expect(describeEvent(ev(1, "approval.requested", { payload: { action_type: "tool:social.publish" } }))).toContain("social.publish");
    expect(describeEvent(ev(1, "tool.call_denied", { payload: { tool_key: "x", error_code: "TOOL_DENIED", reason: "deny_not_granted" } }))).toContain("TOOL_DENIED");
  });
});

describe("P4 events", () => {
  it("describes usage with an estimated cost and refreshes KPIs", () => {
    const e = ev(1, "agent.run.usage_recorded", {
      payload: { run_id: "r1", model: "claude-opus-5-5", input_tokens: 11, output_tokens: 7, cost_usd: 0.000184 },
    });
    expect(describeEvent(e)).toBe("claude-opus-5-5: 11 token vào, 7 token ra · ~0.0002 USD (ước tính)");
    expect(queriesToRefresh(e)).toContainEqual(["kpis", "c1"]);
    const unpriced = ev(2, "agent.run.usage_recorded", {
      payload: { run_id: "r1", model: "gpt-x", input_tokens: 1, output_tokens: 2, cost_usd: null },
    });
    expect(describeEvent(unpriced)).toContain("chưa có giá");
  });
  it("credential events refresh the credential list and never need the secret", () => {
    const e = ev(3, "credential.revoked", { run_id: null, payload: { label: "Key", provider: "anthropic" } });
    expect(describeEvent(e)).toBe('Thu hồi credential "Key"');
    expect(queriesToRefresh(e)).toContainEqual(["credentials"]);
  });
});
