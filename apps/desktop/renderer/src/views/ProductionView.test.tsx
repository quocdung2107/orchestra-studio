import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectDetail } from "./ProductionView";

// Same-origin paths do not parse in Node: point the typed client at an absolute base URL.
vi.mock("../api/client", async (orig) => {
  const mod = await orig<typeof import("../api/client")>();
  const { default: createClient } = await import("openapi-fetch");
  return {
    ...mod,
    api: createClient({ baseUrl: "http://localhost", fetch: (r: Request) => globalThis.fetch(r) }),
  };
});

const project = (image_source: string | null) => ({
  id: "p1",
  company_id: "c1",
  title: "Vì sao bầu trời có màu xanh?",
  profile: "short",
  status: "draft",
  image_source,
  image_source_confirmed_at: null,
  created_at: "2026-11-06T00:00:00Z",
  updated_at: "2026-11-06T00:00:00Z",
  voice_profile_id: "v1",
  voice_profile_name: "Giọng kênh — nữ miền Nam",
  music_asset_id: null,
  music_gain_db: -18,
  last_error: null,
  estimated_duration_s: 52,
  profile_limits: { min_s: 30, max_s: 90 },
  scenes: [
    {
      id: "s1",
      index: 0,
      narration: "Bạn có bao giờ tự hỏi?",
      visual_prompt: "Bầu trời xanh",
      motion: "auto",
      pause_after_s: 0.4,
      image_asset_id: null,
      image_is_placeholder: false,
      segments: [],
    },
  ],
  latest_render: null,
  renders: [],
  jobs: [],
});

function renderDetail() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ProjectDetail projectId="p1" companyId="c1" onBack={() => {}} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

// openapi-fetch builds Request objects from same-origin paths; give Node a base URL.
const NativeRequest = globalThis.Request;
class RelativeRequest extends NativeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(typeof input === "string" && input.startsWith("/") ? `http://localhost${input}` : input, init);
  }
}

describe("ProjectDetail", () => {
  it("asks to confirm the image source first and keeps an image box on every scene", async () => {
    const calls: { url: string; method: string; body?: string }[] = [];
    let source: string | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const req = input instanceof NativeRequest ? input : new RelativeRequest(String(input), init);
        const body = req.method === "POST" ? await req.text() : undefined;
        calls.push({ url: req.url, method: req.method, body });
        if (req.url.endsWith("/image-source")) source = JSON.parse(body!).source;
        return new Response(JSON.stringify(project(source)), { headers: { "content-type": "application/json" } });
      }),
    );
    renderDetail();
    await screen.findByTestId("image-source-chooser");
    expect((screen.getByRole("button", { name: "Sản xuất video" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Thêm ảnh/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/AI cloud/));
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận cách nhận ảnh" }));
    await waitFor(() => expect(screen.queryByTestId("image-source-chooser")).toBeNull());
    expect(calls.some((c) => c.url.endsWith("/image-source") && c.body === '{"source":"cloud"}')).toBe(true);
    expect(screen.getByText(/Tạo ảnh cloud cho 1 cảnh/)).toBeTruthy();
    expect(screen.getByText(/Thêm ảnh/)).toBeTruthy(); // upload box stays in cloud mode too
  });
});
