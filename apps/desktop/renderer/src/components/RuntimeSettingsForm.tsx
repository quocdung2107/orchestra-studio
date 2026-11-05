import { useRuntimes } from "../api/hooks";
import { useCredentials, useRuntimeHealth } from "../api/hooks-p4";
import { inputClass } from "./ui";

export type RuntimeChoice = { runtime_id: string; settings: Record<string, unknown> };

const EFFORTS = ["low", "medium", "high", "xhigh", "max"];

/** Runtime picker + the settings that runtime needs (ADR-0022). Never handles secrets. */
export function RuntimeSettingsForm({
  value,
  onChange,
  companyId,
}: {
  value: RuntimeChoice;
  onChange: (v: RuntimeChoice) => void;
  companyId: string;
}) {
  const runtimes = useRuntimes();
  const creds = useCredentials();
  const rt = runtimes.data?.find((r) => r.runtime_id === value.runtime_id);
  const ollama = useRuntimeHealth("ollama", value.runtime_id === "ollama");
  const s = value.settings;
  const set = (k: string, v: unknown) => {
    const next = { ...s };
    if (v === "" || v === undefined || v === null) delete next[k];
    else next[k] = v;
    onChange({ ...value, settings: next });
  };
  const usable = (creds.data ?? []).filter(
    (c) => c.status === "active" && c.provider === rt?.provider && (!c.company_id || c.company_id === companyId),
  );
  const num = (k: string) => (s[k] === undefined ? "" : String(s[k]));

  return (
    <div className="space-y-2">
      <select
        className={inputClass}
        aria-label="Runtime"
        value={value.runtime_id}
        onChange={(e) => onChange({ runtime_id: e.target.value, settings: {} })}
      >
        {runtimes.data?.map((r) => (
          <option key={r.runtime_id} value={r.runtime_id}>
            {r.display_name}
          </option>
        ))}
      </select>
      {value.runtime_id === "mock" && <p className="text-xs text-slate-500">Mock: chạy theo kịch bản, không gọi AI, không tốn phí.</p>}

      {rt?.requires_credential && (
        <>
          <select className={inputClass} aria-label="Credential" value={String(s.credential_id ?? "")} onChange={(e) => set("credential_id", e.target.value)}>
            <option value="">— Chọn credential {rt.provider} —</option>
            {usable.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} {c.company_id ? "" : "(mọi company)"}
              </option>
            ))}
          </select>
          {usable.length === 0 && (
            <p className="text-xs text-amber-300">Chưa có credential {rt.provider}. Thêm ở mục "Kết nối & model".</p>
          )}
        </>
      )}

      {value.runtime_id !== "mock" && (
        <>
          {value.runtime_id === "ollama" && (ollama.data?.models?.length ?? 0) > 0 ? (
            <select className={inputClass} aria-label="Model" value={String(s.model ?? "")} onChange={(e) => set("model", e.target.value)}>
              <option value="">— Chọn model đã tải —</option>
              {ollama.data!.models!.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name} {m.parameter_size ? `· ${m.parameter_size}` : ""}
                </option>
              ))}
            </select>
          ) : (
            <input
              className={inputClass}
              aria-label="Model"
              placeholder={value.runtime_id === "anthropic" ? "Model (mặc định claude-opus-5-5)" : "Tên model (bắt buộc)"}
              value={String(s.model ?? "")}
              onChange={(e) => set("model", e.target.value.trim())}
            />
          )}
          {value.runtime_id === "anthropic" && (
            <select className={inputClass} aria-label="Effort" value={String(s.effort ?? "medium")} onChange={(e) => set("effort", e.target.value)}>
              {EFFORTS.map((x) => (
                <option key={x} value={x}>
                  effort: {x}
                </option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            <input
              className={inputClass}
              type="number"
              min={1}
              max={30}
              aria-label="Số lượt tối đa"
              placeholder="Lượt tối đa (8)"
              value={num("max_turns")}
              onChange={(e) => set("max_turns", e.target.value ? Number(e.target.value) : "")}
            />
            <input
              className={inputClass}
              type="number"
              aria-label="Max tokens"
              placeholder="max_tokens"
              value={num("max_tokens")}
              onChange={(e) => set("max_tokens", e.target.value ? Number(e.target.value) : "")}
            />
          </div>
          {value.runtime_id === "ollama" && (
            <select
              className={inputClass}
              aria-label="Suy nghĩ"
              value={s.think === true ? "on" : s.think === false ? "off" : ""}
              onChange={(e) => set("think", e.target.value === "on" ? true : e.target.value === "off" ? false : "")}
            >
              <option value="">Suy nghĩ: để model tự quyết (khuyên dùng)</option>
              <option value="on">Suy nghĩ: bật</option>
              <option value="off">Suy nghĩ: tắt (qwen3 trên Ollama có thể còn chậm hơn)</option>
            </select>
          )}
          <p className="text-xs text-slate-500">
            {value.runtime_id === "ollama"
              ? "Chạy trên máy này; không tốn phí API. Run vượt giới hạn đồng thời sẽ xếp hàng."
              : "Gọi API thật và tính phí theo token. Chi phí hiển thị là ước tính."}
          </p>
        </>
      )}
    </div>
  );
}
