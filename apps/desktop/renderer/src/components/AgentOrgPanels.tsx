import type { AccessDecision, AgentDetail, AgentVersion } from "@orchestra/contracts";
import { useState } from "react";
import { useAgentVersions, useAgents } from "../api/hooks";
import {
  useAgentSkills,
  useAttachSkill,
  useCreateAgentVersion,
  useDepartments,
  useDetachSkill,
  useGrantTool,
  useRevokeTool,
  useSkillVersions,
  useSkills,
  useToolAccess,
  useUpdateAgent,
} from "../api/hooks-p1";
import { ErrorView, SecondaryButton, inputClass } from "./ui";

const sel = "w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase text-slate-500 mb-1">{title}</div>
      {children}
    </div>
  );
}

export function PlacementPanel({ companyId, agent }: { companyId: string; agent: AgentDetail }) {
  const depts = useDepartments(companyId);
  const agents = useAgents(companyId);
  const update = useUpdateAgent(companyId);
  const disabled = agent.status === "archived" || update.isPending;
  return (
    <Block title="Vị trí trong tổ chức">
      <label className="text-xs text-slate-400">Phòng ban</label>
      <select
        className={sel}
        disabled={disabled}
        value={agent.department_id ?? ""}
        onChange={(e) => update.mutate({ id: agent.id, body: { department_id: e.target.value || null } })}
      >
        <option value="">— Không thuộc phòng ban —</option>
        {depts.data?.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      <label className="text-xs text-slate-400 mt-2 block">Báo cáo cho</label>
      <select
        className={sel}
        disabled={disabled}
        value={agent.reports_to_agent_id ?? ""}
        onChange={(e) => update.mutate({ id: agent.id, body: { reports_to_agent_id: e.target.value || null } })}
      >
        <option value="">— Không có —</option>
        {agents.data
          ?.filter((a) => a.id !== agent.id)
          .map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.role})
            </option>
          ))}
      </select>
      {update.isError && <ErrorView error={update.error} />}
    </Block>
  );
}

export function SkillsPanel({ companyId, agent }: { companyId: string; agent: AgentDetail }) {
  const attached = useAgentSkills(agent.id);
  const skills = useSkills(companyId);
  const attach = useAttachSkill(agent.id);
  const detach = useDetachSkill(agent.id);
  const [pick, setPick] = useState("");
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const versions = useSkillVersions(upgrading);
  const available = skills.data?.filter((s) => !attached.data?.some((a) => a.skill_id === s.id)) ?? [];
  const latestId = (skillId: string) => versions.data?.find((v) => v.skill_id === skillId)?.id;
  return (
    <Block title="Skills (ghim phiên bản)">
      {attached.data?.length === 0 && <div className="text-slate-500 text-sm">Chưa gắn skill.</div>}
      {attached.data?.map((s) => (
        <div key={s.skill_id} className="flex items-center gap-2 text-sm py-0.5">
          <span className="flex-1">
            {s.skill_name} <span className="text-xs text-slate-400">v{s.version_number}</span>
          </span>
          {s.version_number < s.latest_version_number && (
            <button
              className="text-xs text-amber-300 underline"
              onMouseEnter={() => setUpgrading(s.skill_id)}
              onClick={() => {
                const target = latestId(s.skill_id);
                if (target) attach.mutate({ skill_id: s.skill_id, skill_version_id: target });
                else setUpgrading(s.skill_id);
              }}
            >
              nâng lên v{s.latest_version_number}
            </button>
          )}
          <button className="text-xs text-slate-500 hover:text-red-300" onClick={() => detach.mutate(s.skill_id)}>
            gỡ
          </button>
        </div>
      ))}
      {available.length > 0 && agent.status !== "archived" && (
        <div className="flex gap-2 mt-1">
          <select className={sel} value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">— Chọn skill —</option>
            {available.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} (v{s.latest_version_number})
              </option>
            ))}
          </select>
          <SecondaryButton disabled={!pick || attach.isPending} onClick={() => attach.mutate({ skill_id: pick }, { onSuccess: () => setPick("") })}>
            Gắn
          </SecondaryButton>
        </div>
      )}
      {(attach.isError || detach.isError) && <ErrorView error={attach.error ?? detach.error} />}
    </Block>
  );
}

const RESULT_TEXT: Record<AccessDecision["result"], string> = {
  allow: "được dùng",
  deny_not_granted: "chưa cấp",
  deny_above_ceiling: "bị chặn: vượt trần",
  deny_inactive: "bị chặn: không hoạt động",
};

export function ToolsPanel({ agent }: { agent: AgentDetail }) {
  const access = useToolAccess(agent.id);
  const grant = useGrantTool(agent.id);
  const revoke = useRevokeTool(agent.id);
  const ceiling = access.data?.[0];
  return (
    <Block title="Tools & quyền">
      {ceiling && (
        <div className="text-xs text-slate-400 mb-1">
          Trần hiệu lực: L{ceiling.ceiling} (từ {ceiling.ceiling_source})
        </div>
      )}
      {access.data?.length === 0 && <div className="text-slate-500 text-sm">Company chưa khai báo tool.</div>}
      {access.data?.map((d) => (
        <div key={d.tool_id} className="flex items-center gap-2 text-sm py-0.5">
          <span className="font-mono text-xs flex-1 truncate" title={d.resource}>
            {d.tool_key} <span className="text-slate-500">L{d.tool_level}</span>
            {d.requires_approval && <span className="text-amber-400"> · cần duyệt</span>}
          </span>
          <span className={`text-xs ${d.allowed ? "text-emerald-400" : d.granted ? "text-red-400" : "text-slate-500"}`}>
            {RESULT_TEXT[d.result]}
          </span>
          {d.granted ? (
            <button className="text-xs underline text-slate-400" onClick={() => revoke.mutate(d.tool_id)}>
              thu hồi
            </button>
          ) : (
            <button
              className="text-xs underline text-indigo-300 disabled:opacity-40 disabled:no-underline"
              disabled={d.tool_level > d.ceiling || agent.status === "archived"}
              title={d.tool_level > d.ceiling ? "Vượt trần quyền của agent" : ""}
              onClick={() => grant.mutate(d.tool_id)}
            >
              cấp
            </button>
          )}
        </div>
      ))}
      {(grant.isError || revoke.isError) && <ErrorView error={grant.error ?? revoke.error} />}
    </Block>
  );
}

export function DefinitionPanel({ companyId, agent }: { companyId: string; agent: AgentDetail }) {
  const create = useCreateAgentVersion(companyId, agent.id);
  const current = agent.current_version;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(current?.definition.instructions ?? "");
  if (!current) return null;
  return (
    <Block title={`Định nghĩa · v${current.version_number}`}>
      {!editing ? (
        <>
          <p className="whitespace-pre-wrap text-slate-300 text-sm">{current.definition.instructions || "(chưa có chỉ dẫn)"}</p>
          {agent.status !== "archived" && (
            <button className="text-xs underline text-indigo-300 mt-1" onClick={() => { setText(current.definition.instructions ?? ""); setEditing(true); }}>
              Sửa (tạo phiên bản mới)
            </button>
          )}
        </>
      ) : (
        <div className="space-y-2">
          <textarea className={inputClass} rows={4} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2">
            <SecondaryButton
              disabled={create.isPending || text === current.definition.instructions}
              onClick={() =>
                create.mutate(
                  { definition: { ...current.definition, instructions: text }, runtime: { ...current.runtime, runtime_id: current.runtime.runtime_id ?? "mock" } },
                  { onSuccess: () => setEditing(false) },
                )
              }
            >
              Lưu thành v{current.version_number + 1}
            </SecondaryButton>
            <SecondaryButton onClick={() => setEditing(false)}>Hủy</SecondaryButton>
          </div>
          {create.isError && <ErrorView error={create.error} />}
        </div>
      )}
    </Block>
  );
}

/** Field-level differences between two versions. */
export function diffVersions(a: AgentVersion, b: AgentVersion): { field: string; from: string; to: string }[] {
  const flat = (v: AgentVersion): Record<string, string> => ({
    instructions: v.definition.instructions ?? "",
    goals: (v.definition.goals ?? []).join(", "),
    runtime: v.runtime.runtime_id ?? "",
    runtime_settings: JSON.stringify(v.runtime.settings ?? {}),
  });
  const fa = flat(a);
  const fb = flat(b);
  return Object.keys(fa)
    .filter((k) => fa[k] !== fb[k])
    .map((k) => ({ field: k, from: fa[k], to: fb[k] }));
}

export function VersionComparePanel({ agentId }: { agentId: string }) {
  const versions = useAgentVersions(agentId);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  if (!versions.data || versions.data.length < 2) return null;
  const va = versions.data.find((v) => v.id === a);
  const vb = versions.data.find((v) => v.id === b);
  const diffs = va && vb ? diffVersions(va, vb) : null;
  return (
    <Block title="So sánh phiên bản">
      <div className="flex gap-2">
        {[{ v: a, set: setA }, { v: b, set: setB }].map((x, i) => (
          <select key={i} className={sel} value={x.v} onChange={(e) => x.set(e.target.value)}>
            <option value="">—</option>
            {versions.data!.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
        ))}
      </div>
      {diffs && diffs.length === 0 && <p className="text-xs text-slate-500 mt-1">Không khác nhau.</p>}
      {diffs?.map((d) => (
        <div key={d.field} className="text-xs mt-2">
          <div className="text-slate-400">{d.field}</div>
          <div className="bg-red-950/40 px-1 whitespace-pre-wrap">- {d.from || "(trống)"}</div>
          <div className="bg-emerald-950/40 px-1 whitespace-pre-wrap">+ {d.to || "(trống)"}</div>
        </div>
      ))}
    </Block>
  );
}
