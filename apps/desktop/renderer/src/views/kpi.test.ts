import { describe, expect, it } from "vitest";
import { formatBytes } from "./ConnectionsView";
import { costLabel, duration, pct } from "./KpiView";

describe("KPI formatting", () => {
  it("labels cost as an estimate and counts unpriced runs", () => {
    expect(costLabel({ cost_usd: 0, llm_runs: 0, unpriced_runs: 0 })).toBe("—");
    expect(costLabel({ cost_usd: 0.000368, llm_runs: 1, unpriced_runs: 0 })).toBe("~0.0004 USD");
    expect(costLabel({ cost_usd: 0.01, llm_runs: 3, unpriced_runs: 2 })).toBe("~0.0100 USD (+2 run chưa có giá)");
  });
  it("formats rates, durations and sizes", () => {
    expect(pct(null)).toBe("—");
    expect(pct(0.756)).toBe("76%");
    expect(duration(500)).toBe("500 ms");
    expect(duration(2500)).toBe("2.5 s");
    expect(duration(90_000)).toBe("1.5 phút");
    expect(formatBytes(4_900_000_000)).toBe("4.9 GB");
    expect(formatBytes(undefined)).toBe("—");
  });
});
