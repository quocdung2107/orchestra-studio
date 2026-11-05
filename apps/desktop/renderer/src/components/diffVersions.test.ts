import type { AgentVersion } from "@orchestra/contracts";
import { describe, expect, it } from "vitest";
import { diffVersions } from "./AgentOrgPanels";

const v = (instructions: string, runtime_id = "mock") =>
  ({ definition: { instructions, goals: [] }, runtime: { runtime_id, settings: {} } }) as unknown as AgentVersion;

describe("diffVersions", () => {
  it("returns no differences for equal versions", () => {
    expect(diffVersions(v("a"), v("a"))).toEqual([]);
  });
  it("lists changed fields only", () => {
    expect(diffVersions(v("a"), v("b"))).toEqual([{ field: "instructions", from: "a", to: "b" }]);
    expect(diffVersions(v("a", "mock"), v("a", "other")).map((d) => d.field)).toEqual(["runtime"]);
  });
});
