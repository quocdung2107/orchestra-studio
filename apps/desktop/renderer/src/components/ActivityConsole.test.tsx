import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SelectionProvider } from "../state/selection";
import { ActivityConsole } from "./ActivityConsole";

describe("ActivityConsole", () => {
  it("shows connection state honestly and an empty state", () => {
    render(
      <SelectionProvider>
        <ActivityConsole events={[]} status="reconnecting" open onToggle={() => {}} />
      </SelectionProvider>,
    );
    expect(screen.getByText(/đang thử lại/)).toBeTruthy();
    expect(screen.getByText("Chưa có sự kiện.")).toBeTruthy();
  });
});
