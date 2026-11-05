import { useState } from "react";
import {
  useArchiveTool,
  useCreateSkill,
  useCreateSkillVersion,
  useCreateTool,
  useSkillVersions,
  useSkills,
  useTools,
} from "../api/hooks-p1";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, inputClass } from "../components/ui";

const LEVEL = ["L0 Đọc", "L1 Nháp", "L2 Thực thi", "L3 Hành động ngoài"];

export function CapabilitiesView({ companyId }: { companyId: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Skills & Tools</h1>
      <p className="text-sm text-slate-400 mb-6">
        P1 chỉ khai báo và cấp quyền. Tool chưa được thực thi (Tool Gateway ở P2).
      </p>
      <SkillsSection companyId={companyId} />
      <ToolsSection companyId={companyId} />
    </div>
  );
}

function SkillsSection({ companyId }: { companyId: string }) {
  const skills = useSkills(companyId);
  const create = useCreateSkill(companyId);
  const [open, setOpen] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  return (
    <Section title="Skills">
      {skills.isLoading && <Loading />}
      {skills.isError && <ErrorView error={skills.error} />}
      {skills.data?.length === 0 && <Empty>Chưa có skill.</Empty>}
      <div className="space-y-1 mb-4">
        {skills.data?.map((s) => (
          <div key={s.id} className="border border-slate-800 rounded">
            <button className="w-full text-left px-3 py-2 flex justify-between text-sm" onClick={() => setOpen(open === s.id ? null : s.id)}>
              <span>
                {s.name} <span className="text-slate-500">— {s.description || "không mô tả"}</span>
              </span>
              <span className="text-xs text-slate-400">v{s.latest_version_number}</span>
            </button>
            {open === s.id && <SkillVersions companyId={companyId} skillId={s.id} />}
          </div>
        ))}
      </div>
      <form
        className="space-y-2 max-w-lg"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            { name, description: "", version: { instructions, input_hints: [] } },
            { onSuccess: () => { setName(""); setInstructions(""); } },
          );
        }}
      >
        <input className={inputClass} placeholder="Tên skill mới" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea className={inputClass} rows={2} placeholder="Hướng dẫn (v1)" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        <Button type="submit" disabled={!name.trim() || create.isPending}>Tạo skill</Button>
        {create.isError && <ErrorView error={create.error} />}
      </form>
    </Section>
  );
}

function SkillVersions({ companyId, skillId }: { companyId: string; skillId: string }) {
  const versions = useSkillVersions(skillId);
  const add = useCreateSkillVersion(companyId);
  const [text, setText] = useState("");
  return (
    <div className="px-3 pb-3 text-sm space-y-2">
      {versions.data?.map((v) => (
        <div key={v.id} className="text-xs">
          <span className="text-indigo-300">v{v.version_number}</span>{" "}
          <span className="text-slate-300 whitespace-pre-wrap">{v.instructions || "(trống)"}</span>
        </div>
      ))}
      <textarea className={inputClass} rows={2} placeholder="Hướng dẫn cho phiên bản mới" value={text} onChange={(e) => setText(e.target.value)} />
      <SecondaryButton
        disabled={add.isPending}
        onClick={() => add.mutate({ skillId, instructions: text, input_hints: [] }, { onSuccess: () => setText("") })}
      >
        Tạo phiên bản mới
      </SecondaryButton>
      <p className="text-xs text-slate-500">Agent đang dùng skill này vẫn giữ phiên bản cũ cho tới khi bạn nâng cấp trong Inspector.</p>
      {add.isError && <ErrorView error={add.error} />}
    </div>
  );
}

function ToolsSection({ companyId }: { companyId: string }) {
  const tools = useTools(companyId);
  const create = useCreateTool(companyId);
  const archive = useArchiveTool(companyId);
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [level, setLevel] = useState(0);
  const [approval, setApproval] = useState(false);
  return (
    <Section title="Tools">
      {tools.isLoading && <Loading />}
      {tools.isError && <ErrorView error={tools.error} />}
      {tools.data?.length === 0 && <Empty>Chưa có tool.</Empty>}
      {!!tools.data?.length && (
        <table className="w-full text-sm mb-4">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th className="py-1">Key</th>
              <th>Tên</th>
              <th>Mức quyền</th>
              <th>Chính sách</th>
              <th>v</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tools.data.map((t) => (
              <tr key={t.id} className="border-t border-slate-800">
                <td className="py-1.5 font-mono text-xs">{t.key}</td>
                <td>{t.name}</td>
                <td>{LEVEL[t.permission_level]}</td>
                <td className="text-xs text-slate-400">
                  {t.policy.requires_approval ? "cần duyệt · " : ""}
                  mạng: {t.policy.network}
                  {t.policy.allowed_paths?.length ? ` · path: ${t.policy.allowed_paths.join(", ")}` : ""} · {t.policy.timeout_seconds}s
                </td>
                <td className="text-xs">{t.version}</td>
                <td>
                  <button className="text-xs text-slate-500 hover:text-red-300" onClick={() => archive.mutate(t.id)}>
                    Lưu trữ
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form
        className="grid grid-cols-2 gap-2 max-w-lg"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            { key, name, permission_level: level, policy: { requires_approval: approval || level === 3 } },
            { onSuccess: () => { setKey(""); setName(""); } },
          );
        }}
      >
        <input className={inputClass} placeholder="key (vd: kb.search)" value={key} onChange={(e) => setKey(e.target.value)} />
        <input className={inputClass} placeholder="Tên" value={name} onChange={(e) => setName(e.target.value)} />
        <select className={inputClass} value={level} onChange={(e) => setLevel(Number(e.target.value))}>
          {LEVEL.map((l, i) => (
            <option key={l} value={i}>
              {l}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={approval || level === 3} disabled={level === 3} onChange={(e) => setApproval(e.target.checked)} />
          Cần phê duyệt
        </label>
        <Button type="submit" disabled={!key.trim() || !name.trim() || create.isPending}>Khai báo tool</Button>
        {create.isError && <div className="col-span-2"><ErrorView error={create.error} /></div>}
      </form>
    </Section>
  );
}
