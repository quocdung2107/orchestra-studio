import { describe, expect, it } from "vitest";
import { ApiRequestError, toApiError, unwrap } from "./client";

describe("API errors", () => {
  it("maps structured backend errors", () => {
    const e = toApiError(409, { error: { code: "invalid_state", message: "Agent is archived" } });
    expect(e.code).toBe("invalid_state");
    expect(e.status).toBe(409);
  });

  it("reports an unreachable backend instead of a generic error", () => {
    expect(toApiError(502, undefined).code).toBe("backend_unreachable");
  });

  it("unwrap throws on non-ok responses even without a body", () => {
    expect(() => unwrap({ data: {}, response: new Response(null, { status: 500 }) })).toThrow(ApiRequestError);
  });
});
