import { useState } from "react";
import { useCreatePairing, useRevokeWorker, useWorkers } from "../api/hooks-p5";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, formatTime, inputClass } from "../components/ui";

/** Paired worker processes (ADR-0025): pair, see heartbeat, revoke. */
export function WorkersView() {
  const workers = useWorkers();
  const pairing = useCreatePairing();
  const revoke = useRevokeWorker();
  const [name, setName] = useState("Worker máy này");

  return (
    <div className="max-w-3xl">
      <Section title="Ghép nối worker">
        <p className="text-sm text-slate-400 mb-2">
          Worker là tiến trình riêng nhận việc từ app và chạy agent bằng Mock hoặc Ollama. Nó tự kết nối tới app, có danh
          tính riêng và có thể bị thu hồi. Mất liên lạc quá lâu thì run thất bại, không bao giờ bị tính là xong.
        </p>
        <div className="flex gap-2">
          <input className={inputClass} aria-label="Tên worker" value={name} onChange={(e) => setName(e.target.value)} />
          <Button disabled={pairing.isPending || !name.trim()} onClick={() => pairing.mutate(name.trim())}>
            Tạo mã ghép nối
          </Button>
        </div>
        {pairing.isError && <ErrorView error={pairing.error} />}
        {pairing.data && (
          <div className="mt-3 rounded border border-indigo-800 bg-indigo-950/40 p-3 text-sm" data-testid="pairing-code">
            <div>
              Mã: <span className="font-mono text-lg tracking-widest">{pairing.data.code}</span> (dùng một lần, hết hạn lúc{" "}
              {formatTime(pairing.data.expires_at)})
            </div>
            <div className="mt-2 text-slate-400">Mở cửa sổ lệnh trong thư mục dự án và chạy:</div>
            <pre className="mt-1 bg-slate-900 border border-slate-800 rounded p-2 text-xs">{pairing.data.command}{"\n"}pnpm worker</pre>
          </div>
        )}
      </Section>

      <Section title="Workers">
        {workers.isLoading ? (
          <Loading />
        ) : workers.isError ? (
          <ErrorView error={workers.error} onRetry={() => workers.refetch()} />
        ) : (workers.data ?? []).length === 0 ? (
          <Empty>Chưa ghép nối worker nào.</Empty>
        ) : (
          <ul className="divide-y divide-slate-800 text-sm">
            {workers.data!.map((w) => (
              <li key={w.id} className="py-2 flex items-start justify-between gap-4">
                <div>
                  <div className="font-medium">
                    {w.name}{" "}
                    <span
                      className={
                        w.status === "revoked" ? "text-red-300" : w.online ? "text-emerald-300" : "text-slate-500"
                      }
                    >
                      ● {w.status === "revoked" ? "đã thu hồi" : w.online ? "đang kết nối" : "không kết nối"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    {w.hostname || "?"} · {w.platform || "?"} · runtime: {w.runtimes.join(", ") || "—"} · lần cuối:{" "}
                    {formatTime(w.last_seen_at)}
                    {w.active_leases > 0 && ` · đang chạy ${w.active_leases} việc`}
                  </div>
                </div>
                {w.status !== "revoked" && (
                  <SecondaryButton
                    disabled={revoke.isPending}
                    onClick={() => {
                      if (window.confirm(`Thu hồi ${w.name}? Việc đang chạy trên worker này sẽ thất bại.`)) revoke.mutate(w.id);
                    }}
                  >
                    Thu hồi
                  </SecondaryButton>
                )}
              </li>
            ))}
          </ul>
        )}
        {revoke.isError && <ErrorView error={revoke.error} />}
      </Section>
    </div>
  );
}
