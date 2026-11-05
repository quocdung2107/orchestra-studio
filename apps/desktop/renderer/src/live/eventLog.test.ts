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
    expect(queriesToRefresh(ev(1, "agent.run.completed"))).toEqual([["runs", "c1"], ["run", "r1"], ["runEvents", "r1"]]);
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
