import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import {
  fetchVoices,
  previewNormalize,
  useEngines,
  useMediaSettings,
  useProviders,
  useSaveMediaSettings,
  useUpdateVoiceProfile,
  useVoiceProfiles,
  type MediaSettings,
  type VoiceProfile,
} from "../api/hooks-video";
import { Button, ErrorView, Loading, SecondaryButton, Section, inputClass } from "../components/ui";

/** Engines, voice profile, cloud images, ASR, encoder (ADR-0029..0032). */
export function MediaSettingsView({ companyId }: { companyId: string }) {
  return (
    <div className="max-w-4xl">
      <EnginesPanel />
      <VoicePanel companyId={companyId} />
      <SettingsPanel companyId={companyId} />
      <ProvidersPanel />
    </div>
  );
}

function EnginesPanel() {
  const q = useEngines();
  return (
    <Section title="Engine cục bộ">
      {q.isLoading ? (
        <Loading />
      ) : q.isError ? (
        <ErrorView error={q.error} onRetry={() => q.refetch()} />
      ) : (
        <ul className="divide-y divide-slate-800 text-sm">
          {q.data!.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex justify-between gap-2">
                <span>{e.label || e.id}</span>
                <span className={e.running ? "text-emerald-300" : "text-slate-400"}>
                  {e.running ? "đang chạy" : "chưa chạy"} · {e.base_url}
                  {e.managed ? " · Orchestra tự bật" : " · tự mở ngoài app"}
                </span>
              </div>
              {!e.running && <p className="text-xs text-slate-500 mt-0.5">{e.install_hint}</p>}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-slate-500 mt-2">
        Engine chạy ở tiến trình riêng, chỉ nghe 127.0.0.1. Hướng dẫn cài: docs/MEDIA_ENGINES.md.
      </p>
    </Section>
  );
}

function VoicePanel({ companyId }: { companyId: string }) {
  const q = useVoiceProfiles(companyId);
  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorView error={q.error} onRetry={() => q.refetch()} />;
  const p = q.data!.find((x) => x.is_default) ?? q.data![0];
  return p ? <VoiceEditor key={`${p.id}-${p.current_version}`} profile={p} companyId={companyId} /> : null;
}

function VoiceEditor({ profile, companyId }: { profile: VoiceProfile; companyId: string }) {
  const cur = profile.current;
  const [engine, setEngine] = useState(cur.engine as "vieneu" | "zerotts" | "fake_tts");
  const [voice, setVoice] = useState(cur.voice);
  const [dialect, setDialect] = useState(cur.dialect as "south" | "north");
  const [speed, setSpeed] = useState(cur.speed);
  const [lexicon, setLexicon] = useState(
    Object.entries(cur.lexicon_json as Record<string, string>)
      .map(([k, v]) => `${k} = ${v}`)
      .join("\n"),
  );
  const [voices, setVoices] = useState<{ id: string; name?: string; gender?: string }[] | null>(null);
  const [voiceErr, setVoiceErr] = useState<string | null>(null);
  const [sample, setSample] = useState("Ngày 02/09/1945, lúc 14h30, giá 1.250.000đ, tăng 25%. Mô hình AI chạy trên GPU.");
  const [preview, setPreview] = useState<string | null>(null);
  const save = useUpdateVoiceProfile(companyId);

  const lex = Object.fromEntries(
    lexicon
      .split("\n")
      .map((l) => l.split("="))
      .filter((p) => p.length === 2 && p[0].trim() && p[1].trim())
      .map(([k, v]) => [k.trim(), v.trim()]),
  );

  return (
    <Section title={`Giọng kênh: ${profile.name} (v${profile.current_version})`}>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <label>
          Engine
          <select className={inputClass} value={engine} onChange={(e) => setEngine(e.target.value as typeof engine)}>
            <option value="vieneu">VieNeu-TTS v3 Turbo (chính)</option>
            <option value="zerotts">ZeroTTS (phụ, CPU nhanh)</option>
            <option value="fake_tts">Giọng giả (thử pipeline)</option>
          </select>
        </label>
        <label>
          Giọng
          <div className="flex gap-2">
            {voices ? (
              <select className={inputClass} value={voice} onChange={(e) => setVoice(e.target.value)}>
                {!voices.some((v) => v.id === voice) && <option value={voice}>{voice}</option>}
                {voices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name ?? v.id}
                    {v.gender ? ` (${v.gender})` : ""}
                  </option>
                ))}
              </select>
            ) : (
              <input className={inputClass} value={voice} onChange={(e) => setVoice(e.target.value)} />
            )}
            <SecondaryButton
              onClick={async () => {
                setVoiceErr(null);
                try {
                  setVoices((await fetchVoices(engine)) as { id: string }[]);
                } catch (e) {
                  setVoiceErr(errorMessage(e));
                }
              }}
            >
              Lấy danh sách
            </SecondaryButton>
          </div>
          {voiceErr && <span className="text-xs text-red-300">{voiceErr}</span>}
        </label>
        <label>
          Phương ngữ khi đọc số
          <select className={inputClass} value={dialect} onChange={(e) => setDialect(e.target.value as typeof dialect)}>
            <option value="south">Miền Nam (ngàn, lẻ)</option>
            <option value="north">Miền Bắc (nghìn, linh)</option>
          </select>
        </label>
        <label>
          Tốc độ ({speed.toFixed(2)}×)
          <input type="range" min={0.8} max={1.25} step={0.05} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="w-full" />
        </label>
        <label className="col-span-2">
          Từ điển phát âm của kênh (mỗi dòng: <code>từ = cách đọc</code>)
          <textarea className={`${inputClass} font-mono h-20`} value={lexicon} onChange={(e) => setLexicon(e.target.value)} />
        </label>
        <label className="col-span-2">
          Thử chuẩn hóa văn bản
          <div className="flex gap-2">
            <input className={inputClass} value={sample} onChange={(e) => setSample(e.target.value)} />
            <SecondaryButton onClick={async () => setPreview((await previewNormalize(sample, dialect, lex)).normalized)}>
              Xem
            </SecondaryButton>
          </div>
          {preview && <p className="text-slate-300 mt-1">{preview}</p>}
        </label>
      </div>
      {save.isError && <ErrorView error={save.error} />}
      <Button
        className="mt-3"
        disabled={save.isPending}
        onClick={() =>
          save.mutate({
            id: profile.id,
            body: { engine, voice, dialect, speed, lexicon: lex, max_chars: cur.max_chars, params: cur.params_json as Record<string, number> },
          })
        }
      >
        Lưu thành phiên bản mới
      </Button>
      <p className="text-xs text-slate-500 mt-1">
        Video đang làm sẽ dùng phiên bản mới ở lần bấm “Sản xuất video” tiếp theo (chỉ đọc lại các cảnh bị ảnh hưởng).
      </p>
    </Section>
  );
}

function SettingsPanel({ companyId }: { companyId: string }) {
  const q = useMediaSettings(companyId);
  const save = useSaveMediaSettings(companyId);
  const [s, setS] = useState<MediaSettings | null>(null);
  useEffect(() => {
    if (q.data) setS(q.data);
  }, [q.data]);
  if (q.isLoading || !s) return <Loading />;
  if (q.isError) return <ErrorView error={q.error} />;
  const ci = s.cloud_image!;
  const setCi = (patch: Partial<typeof ci>) => setS({ ...s, cloud_image: { ...ci, ...patch } });
  return (
    <Section title="Cài đặt sản xuất">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <label>
          Encoder video
          <select className={inputClass} value={s.encoder} onChange={(e) => setS({ ...s, encoder: e.target.value as MediaSettings["encoder"] })}>
            <option value="libx264">libx264 (CPU, mặc định)</option>
            <option value="h264_nvenc">h264_nvenc (GPU NVIDIA)</option>
          </select>
        </label>
        <label>
          Font phụ đề
          <input className={inputClass} value={s.subtitle_font} onChange={(e) => setS({ ...s, subtitle_font: e.target.value })} />
        </label>
        <label>
          Kiểm tra lời đọc bằng ASR
          <select className={inputClass} value={s.asr_provider} onChange={(e) => setS({ ...s, asr_provider: e.target.value as MediaSettings["asr_provider"] })}>
            <option value="none">Tắt</option>
            <option value="faster_whisper">faster-whisper (local)</option>
            <option value="fake_asr">ASR giả (thử)</option>
          </select>
        </label>
        <label className="flex items-center gap-2 mt-5">
          <input type="checkbox" checked={s.burn_subtitles} onChange={(e) => setS({ ...s, burn_subtitles: e.target.checked })} />
          Đốt phụ đề vào video
        </label>
      </div>
      <h3 className="text-sm font-medium mt-4 mb-1">Ảnh AI cloud (API kiểu OpenAI /images/generations)</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <label>
          Base URL (https)
          <input className={inputClass} placeholder="https://…/v1" value={ci.base_url} onChange={(e) => setCi({ base_url: e.target.value })} />
        </label>
        <label>
          Model
          <input className={inputClass} value={ci.model} onChange={(e) => setCi({ model: e.target.value })} />
        </label>
        <label>
          Kích thước
          <input className={inputClass} value={ci.size} onChange={(e) => setCi({ size: e.target.value })} />
        </label>
        <label>
          Credential ID (loại image_api, ở “Kết nối & model”)
          <input className={inputClass} value={ci.credential_id ?? ""} onChange={(e) => setCi({ credential_id: e.target.value || null })} />
        </label>
        <label className="col-span-2 flex items-center gap-2">
          <input type="checkbox" checked={ci.commercial_use_confirmed} onChange={(e) => setCi({ commercial_use_confirmed: e.target.checked })} />
          Tôi đã đọc điều khoản: ảnh tạo ra được phép dùng cho kênh (thương mại). Chưa tick thì app chặn.
        </label>
      </div>
      {save.isError && <ErrorView error={save.error} />}
      {save.isSuccess && <p className="text-sm text-emerald-300 mt-2">Đã lưu</p>}
      <Button className="mt-3" disabled={save.isPending} onClick={() => save.mutate(s)}>
        Lưu cài đặt
      </Button>
    </Section>
  );
}

function ProvidersPanel() {
  const q = useProviders();
  if (!q.data) return null;
  return (
    <Section title="Provider và license">
      <ul className="text-xs space-y-1">
        {q.data.map((p) => (
          <li key={p.provider_id} className={p.allowed ? "text-slate-300" : "text-red-300"}>
            {p.label || p.provider_id} · {String(p.license.code)} / {String(p.license.weights)}
            {p.fake ? " · giả lập" : ""}
            {!p.allowed && ` · bị chặn: ${p.blocked_reason}`}
          </li>
        ))}
      </ul>
    </Section>
  );
}
