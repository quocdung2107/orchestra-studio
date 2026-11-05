import type { Credential, RuntimeInfo } from "@orchestra/contracts";
import { useState } from "react";
import { useRuntimes } from "../api/hooks";
import {
  useCreateCredential,
  useCredentials,
  useRevokeCredential,
  useRotateCredential,
  useRuntimeHealth,
  useSecretStore,
  useVerifyCredential,
} from "../api/hooks-p4";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge, formatTime, inputClass } from "../components/ui";

export function formatBytes(n: number | undefined | null): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(0)} MB`;
  return `${n} B`;
}

export function ConnectionsView({ companyId }: { companyId: string }) {
  const runtimes = useRuntimes();
  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-semibold mb-1">Kết nối & model</h1>
      <p className="text-sm text-slate-400 mb-4">
        Runtime quyết định agent chạy bằng gì. Mock là mặc định. API key nằm trong kho bảo mật của hệ điều hành; ứng dụng chỉ giữ tham chiếu và không bao giờ hiển thị lại key.
      </p>
      <Section title="Runtime">
        {runtimes.isLoading && <Loading />}
        <div className="grid gap-3 md:grid-cols-2">
          {runtimes.data?.map((r) => (
            <RuntimeCard key={r.runtime_id} rt={r} />
          ))}
        </div>
      </Section>
      <CredentialsSection companyId={companyId} />
    </div>
  );
}

function RuntimeCard({ rt }: { rt: RuntimeInfo }) {
  const caps = Object.entries(rt.capabilities)
    .filter(([, v]) => v)
    .map(([k]) => k.replace("supports_", ""));
  return (
    <div className="p-3 rounded border border-slate-800 text-sm space-y-1">
      <div className="font-medium">{rt.display_name}</div>
      <div className="text-xs text-slate-500 font-mono">{rt.runtime_id}</div>
      <div className="text-xs text-slate-400">Hỗ trợ: {caps.join(", ") || "—"}</div>
      {rt.requires_credential && <div className="text-xs text-slate-400">Cần credential {rt.provider}</div>}
      {rt.runtime_id === "ollama" && <OllamaResources />}
    </div>
  );
}

function OllamaResources() {
  const h = useRuntimeHealth("ollama");
  if (h.isLoading) return <Loading label="Đang hỏi Ollama…" />;
  if (h.isError) return <ErrorView error={h.error} />;
  const d = h.data!;
  return (
    <div className="mt-2 space-y-2 text-xs" data-testid="ollama-resources">
      <div>
        <StatusBadge status={d.status === "ok" ? "active" : "failed"} />{" "}
        {d.status === "ok" ? `Ollama ${d.version ?? ""} tại ${d.base_url}` : (d.detail ?? "Không kết nối được")}
      </div>
      {d.limits && (
        <div className="text-slate-300">
          Giới hạn đồng thời: <b>{d.limits.max_concurrency}</b> · đang chạy {d.limits.running} · đang chờ {d.limits.waiting}
        </div>
      )}
      {d.status === "ok" && (
        <>
          <div>
            <div className="text-slate-500">Model đã tải về ({d.models?.length ?? 0})</div>
            {d.models?.map((m) => (
              <div key={m.name} className="text-slate-300">
                {m.name} · {formatBytes(m.size_bytes)} {m.parameter_size && `· ${m.parameter_size}`} {m.quantization && `· ${m.quantization}`}
              </div>
            ))}
          </div>
          <div>
            <div className="text-slate-500">Đang nạp trong bộ nhớ</div>
            {(d.loaded?.length ?? 0) === 0 && <div className="text-slate-400">Không có</div>}
            {d.loaded?.map((m) => (
              <div key={m.name} className="text-slate-300">
                {m.name} · RAM {formatBytes(m.size_bytes)} · VRAM {formatBytes(m.vram_bytes)}
                {m.context_length ? ` · ctx ${m.context_length}` : ""}
              </div>
            ))}
          </div>
        </>
      )}
      {d.status !== "ok" && (
        <p className="text-slate-500">Cài Ollama và chạy <code>ollama pull &lt;model&gt;</code> nếu muốn dùng model cục bộ.</p>
      )}
    </div>
  );
}

function CredentialsSection({ companyId }: { companyId: string }) {
  const creds = useCredentials();
  const store = useSecretStore();
  const [adding, setAdding] = useState(false);
  return (
    <Section title="Credential" actions={<SecondaryButton onClick={() => setAdding((x) => !x)}>{adding ? "Đóng" : "Thêm"}</SecondaryButton>}>
      {store.data && (
        <p className={`text-xs mb-2 ${store.data.secure ? "text-slate-400" : "text-amber-300"}`}>
          Kho secret: {store.data.description}
          {!store.data.secure && " — không an toàn, chỉ để thử"}
        </p>
      )}
      {adding && <AddCredentialForm companyId={companyId} onDone={() => setAdding(false)} />}
      {creds.isLoading && <Loading />}
      {creds.isError && <ErrorView error={creds.error} />}
      {creds.data?.length === 0 && <Empty>Chưa có credential. Agent dùng Claude/OpenAI cần một credential.</Empty>}
      <div className="space-y-2">
        {creds.data
          ?.filter((c) => !c.company_id || c.company_id === companyId)
          .map((c) => (
            <CredentialRow key={c.id} c={c} />
          ))}
      </div>
    </Section>
  );
}

function CredentialRow({ c }: { c: Credential }) {
  const verify = useVerifyCredential();
  const revoke = useRevokeCredential();
  const rotate = useRotateCredential();
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const active = c.status === "active";
  return (
    <div className="p-3 rounded border border-slate-800 text-sm space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <StatusBadge status={active ? "active" : "archived"} />
        <span className="font-medium">{c.label}</span>
        <span className="text-xs text-slate-400">{c.provider}</span>
        <span className="text-xs text-slate-500">{c.company_id ? "company này" : "mọi company"}</span>
        <span className="text-xs text-slate-500">{c.store === "env" ? `biến môi trường ${c.env_var}` : `kho: ${c.store}`}</span>
      </div>
      <div className="text-xs text-slate-500">
        Tạo {formatTime(c.created_at)}
        {c.rotated_at && ` · xoay ${formatTime(c.rotated_at)}`}
        {c.revoked_at && ` · thu hồi ${formatTime(c.revoked_at)}`}
        {c.last_verified_at && (
          <span className={c.last_verify_ok ? "text-emerald-400" : "text-red-400"}>
            {" "}· kiểm tra {formatTime(c.last_verified_at)}: {c.last_verify_message}
          </span>
        )}
      </div>
      {active && (
        <div className="flex gap-2 flex-wrap items-center">
          <SecondaryButton disabled={verify.isPending} onClick={() => verify.mutate(c.id)}>
            {verify.isPending ? "Đang kiểm tra…" : "Kiểm tra"}
          </SecondaryButton>
          {c.store !== "env" && newSecret === null && <SecondaryButton onClick={() => setNewSecret("")}>Xoay key</SecondaryButton>}
          {newSecret !== null && (
            <>
              <input
                type="password"
                autoComplete="off"
                className={`${inputClass} max-w-xs`}
                placeholder="Key mới"
                value={newSecret}
                onChange={(e) => setNewSecret(e.target.value)}
              />
              <SecondaryButton
                disabled={rotate.isPending || newSecret.length < 8}
                onClick={() => rotate.mutate({ id: c.id, secret: newSecret }, { onSuccess: () => setNewSecret(null) })}
              >
                Lưu
              </SecondaryButton>
              <SecondaryButton onClick={() => setNewSecret(null)}>Hủy</SecondaryButton>
            </>
          )}
          <SecondaryButton
            disabled={revoke.isPending}
            onClick={() => {
              if (window.confirm(`Thu hồi "${c.label}"? Agent đang dùng sẽ không chạy được.`)) revoke.mutate(c.id);
            }}
          >
            Thu hồi
          </SecondaryButton>
        </div>
      )}
      {[verify.error, revoke.error, rotate.error].filter(Boolean).map((e, i) => (
        <ErrorView key={i} error={e} />
      ))}
    </div>
  );
}

function AddCredentialForm({ companyId, onDone }: { companyId: string; onDone: () => void }) {
  const create = useCreateCredential();
  const [provider, setProvider] = useState<"anthropic" | "openai">("anthropic");
  const [label, setLabel] = useState("");
  const [source, setSource] = useState<"secret" | "env">("secret");
  const [secret, setSecret] = useState("");
  const [envVar, setEnvVar] = useState("");
  const [scoped, setScoped] = useState(false);
  const valid = label.trim() && (source === "secret" ? secret.length >= 8 : /^[A-Za-z_][A-Za-z0-9_]*$/.test(envVar));
  return (
    <form
      className="mb-4 p-3 rounded border border-slate-800 space-y-2 max-w-lg"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(
          {
            provider,
            label: label.trim(),
            company_id: scoped ? companyId : null,
            ...(source === "secret" ? { secret } : { env_var: envVar }),
          },
          {
            onSuccess: () => {
              setSecret("");
              onDone();
            },
          },
        );
      }}
    >
      <select className={inputClass} aria-label="Provider" value={provider} onChange={(e) => setProvider(e.target.value as "anthropic" | "openai")}>
        <option value="anthropic">Anthropic (Claude)</option>
        <option value="openai">OpenAI</option>
      </select>
      <input className={inputClass} placeholder="Tên gợi nhớ (ví dụ: Key cá nhân)" value={label} onChange={(e) => setLabel(e.target.value)} />
      <div className="flex gap-4 text-sm">
        <label>
          <input type="radio" checked={source === "secret"} onChange={() => setSource("secret")} /> Nhập key (lưu vào kho của OS)
        </label>
        <label>
          <input type="radio" checked={source === "env"} onChange={() => setSource("env")} /> Đọc từ biến môi trường
        </label>
      </div>
      {source === "secret" ? (
        <input
          type="password"
          autoComplete="off"
          className={inputClass}
          aria-label="API key"
          placeholder="API key"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
        />
      ) : (
        <input className={inputClass} placeholder="Tên biến, ví dụ ANTHROPIC_API_KEY" value={envVar} onChange={(e) => setEnvVar(e.target.value.trim())} />
      )}
      <label className="text-sm block">
        <input type="checkbox" checked={scoped} onChange={(e) => setScoped(e.target.checked)} /> Chỉ dùng cho company này
      </label>
      <Button type="submit" disabled={!valid || create.isPending}>
        Lưu credential
      </Button>
      {create.isError && <ErrorView error={create.error} />}
    </form>
  );
}
