import type { OrgGraph } from "@orchestra/contracts";
import { describe, expect, it } from "vitest";
import { autoLayout, departmentColors } from "./orgLayout";

const agent = (id: string, reports_to_agent_id: string | null) => ({ id, reports_to_agent_id }) as OrgGraph["agents"][number];

describe("autoLayout", () => {
  it("places managers above reports, one row per depth", () => {
    const g = { agents: [agent("ceo", null), agent("a", "ceo"), agent("b", "ceo"), agent("c", "a")], departments: [] } as unknown as OrgGraph;
    const pos = autoLayout(g);
    expect(pos["agent:ceo"].y).toBeLessThan(pos["agent:a"].y);
    expect(pos["agent:a"].y).toBe(pos["agent:b"].y);
    expect(pos["agent:c"].y).toBeGreaterThan(pos["agent:a"].y);
    expect(pos["agent:a"].x).not.toBe(pos["agent:b"].x);
  });

  it("treats a manager outside the graph as root", () => {
    const pos = autoLayout({ agents: [agent("x", "missing")], departments: [] } as unknown as OrgGraph);
    expect(pos["agent:x"]).toEqual({ x: 0, y: 0 });
  });

  it("assigns distinct colors per department", () => {
    const c = departmentColors({ agents: [], departments: [{ id: "d1" }, { id: "d2" }] } as unknown as OrgGraph);
    expect(c.d1).not.toBe(c.d2);
  });
});
