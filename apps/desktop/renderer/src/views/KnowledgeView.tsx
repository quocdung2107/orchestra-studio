import type { KnowledgeItem, RoleProposal } from "@orchestra/contracts";
import { useState } from "react";
import { useAgents } from "../api/hooks";
import { useDepartments } from "../api/hooks-p1";
import {
  useArchiveNote,
  useCreateNote,
  useKnowledge,
  useKnowledgeSearch,
  useLessons,
  useProposeLesson,
  useReviewLesson,
  useReviewRoleProposal,
  useRoleProposals,
  useUpdateNote,
} from "../api/hooks-p2";
import { Button, Empty, ErrorView, Loading, SecondaryButton, Section, StatusBadge, formatTime, inputClass } from "../components/ui";

type Tab = "items" | "lessons" | "proposals";

const SOURCE_TEXT: Record<string, string> = {
  manual: "nhập tay",
  artifact: "từ artifact",
  task_summary: "tóm tắt task",
  lesson: "bài học đã duyệt",
};

export function KnowledgeView({ companyId }: { companyId: string }) {
  const [tab, setTab] = useState<Tab>("items");
  const lessons = useLessons(companyId);
  const proposals = useRoleProposals(companyId);
  const pendingLessons = lessons.data?.filter((l) => l.review_status === "proposed").length ?? 0;
  const pendingProps = proposals.data?.filter((p) => p.status === "proposed").length ?? 0;
  const tabs: [Tab, string][] = [
    ["items", "Kho tri thức"],
    ["lessons", `Bài học${pendingLessons ? ` (${pendingLessons})` : ""}`],
    ["proposals", `Đề xuất đổi vai trò${pendingProps ? ` (${pendingProps})` : ""}`],
  ];
  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-semibold mb-3">Tri thức</h1>
      <div className="flex gap-1 mb-4 border-b border-slate-800" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k}
            className={`px-3 py-1.5 text-sm ${tab === k ? "border-b-2 border-indigo-400 text-slate-100" : "text-slate-400"}`}
            onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "items" && <ItemsTab companyId={companyId} />}
      {tab === "lessons" && <LessonsTab companyId={companyId} />}
      {tab === "proposals" && <ProposalsTab companyId={companyId} />}
    </div>
  );
}

function ItemsTab({ companyId }: { companyId: string }) {
  const items = useKnowledge(companyId);
  const [q, setQ] = useState("");
  const search = useKnowledgeSearch(companyId, q);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const open = items.data?.find((i) => i.id === openId) ?? null;
  return (
    <div className="grid grid-cols-[1fr_1fr] gap-6">
      <div>
        <input className={inputClass} placeholder="Tìm (gõ không dấu cũng được)…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Tìm tri thức" />
        {q.trim() && (
          <div className="mt-2">
            {search.isLoading && <Loading label="Đang tìm…" />}
            {search.isError && <ErrorView error={search.error} />}
            {search.data && (
              <>
                <p className="text-xs text-slate-500 mb-1">{search.data.hits.length} kết quả · {search.data.engine}</p>
                {search.data.hits.map((h) => (
                  <button key={h.id} onClick={() => setOpenId(h.id)} className="block w-full text-left p-2 rounded hover:bg-slate-900">
                    <div className="text-sm">{h.title}</div>
                    <div className="text-xs text-slate-400">{h.snippet}</div>
                  </button>
                ))}
              </>
            )}
          </div>
        )}
        {!q.trim() && (
          <Section title="Tất cả" actions={<button className="text-xs underline" onClick={() => setShowForm((v) => !v)}>{showForm ? "Đóng" : "+ Ghi chú"}</button>}>
            {showForm && <NoteForm companyId={companyId} onDone={() => setShowForm(false)} />}
            {items.isLoading && <Loading />}
            {items.isError && <ErrorView error={items.error} />}
            {items.data?.length === 0 && <Empty>Chưa có tri thức. Thêm ghi chú, lưu artifact từ Inspector, tóm tắt task, hoặc duyệt bài học.</Empty>}
            {items.data?.map((i) => (
              <button key={i.id} onClick={() => setOpenId(i.id)} className={`block w-full text-left p-2 rounded hover:bg-slate-900 ${openId === i.id ? "bg-slate-900" : ""}`}>
                <div className="text-sm">{i.title}</div>
                <div className="text-xs text-slate-500">{i.kind} · {SOURCE_TEXT[i.source_type]} · v{i.version}</div>
              </button>
            ))}
          </Section>
        )}
      </div>
      <div>{open ? <ItemDetail key={open.id + open.version} companyId={companyId} item={open} onArchived={() => setOpenId(null)} /> : <p className="text-sm text-slate-500">Chọn một mục để xem.</p>}</div>
    </div>
  );
}

function NoteForm({ companyId, onDone }: { companyId: string; onDone: () => void }) {
  const create = useCreateNote(companyId);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  return (
    <form className="space-y-2 mb-3" onSubmit={(e) => { e.preventDefault(); create.mutate({ title, content }, { onSuccess: onDone }); }}>
      <input className={inputClass} placeholder="Tiêu đề" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className={inputClass} rows={4} placeholder="Nội dung" value={content} onChange={(e) => setContent(e.target.value)} />
      <Button type="submit" disabled={create.isPending || !title.trim() || !content.trim()}>Lưu ghi chú</Button>
      {create.isError && <ErrorView error={create.error} />}
    </form>
  );
}

function ItemDetail({ companyId, item, onArchived }: { companyId: string; item: KnowledgeItem; onArchived: () => void }) {
  const update = useUpdateNote(companyId);
  const archive = useArchiveNote(companyId);
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(item.content);
  return (
    <div className="space-y-2 text-sm">
      <h2 className="font-semibold">{item.title}</h2>
      <div className="text-xs text-slate-400">
        {item.kind} · v{item.version} · nguồn: {SOURCE_TEXT[item.source_type]}
        {item.source_id && <span className="font-mono"> {item.source_id.slice(0, 8)}</span>} · bởi {item.created_by} · {formatTime(item.updated_at)}
      </div>
      {editing ? (
        <>
          <textarea className={inputClass} rows={10} value={content} onChange={(e) => setContent(e.target.value)} />
          <div className="flex gap-2">
            <Button disabled={update.isPending || content === item.content} onClick={() => update.mutate({ id: item.id, content }, { onSuccess: () => setEditing(false) })}>
              Lưu thành v{item.version + 1}
            </Button>
            <SecondaryButton onClick={() => setEditing(false)}>Hủy</SecondaryButton>
          </div>
        </>
      ) : (
        <pre className="p-3 bg-slate-900 rounded text-xs whitespace-pre-wrap">{item.content}</pre>
      )}
      {!editing && (
        <div className="flex gap-3 text-xs">
          <button className="underline text-indigo-300" onClick={() => setEditing(true)}>Sửa</button>
          <button className="underline text-slate-400" onClick={() => archive.mutate(item.id, { onSuccess: onArchived })}>Lưu trữ</button>
        </div>
      )}
      {(update.isError || archive.isError) && <ErrorView error={update.error ?? archive.error} />}
    </div>
  );
}

function LessonsTab({ companyId }: { companyId: string }) {
  const lessons = useLessons(companyId);
  const review = useReviewLesson(companyId);
  const propose = useProposeLesson(companyId);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">Bài học do agent hoặc bạn đề xuất chỉ thành tri thức sau khi được duyệt.</p>
      {lessons.isLoading && <Loading />}
      {lessons.isError && <ErrorView error={lessons.error} />}
      {lessons.data?.length === 0 && <Empty>Chưa có bài học. Chạy kịch bản P2 để Thư ký đề xuất, hoặc thêm bên dưới.</Empty>}
      {lessons.data?.map((l) => (
        <div key={l.id} className="p-3 rounded border border-slate-800 text-sm space-y-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={l.review_status} />
            <b>{l.title}</b>
            <span className="text-xs text-slate-500 ml-auto">đề xuất bởi {l.proposed_by.startsWith("agent:") ? "agent" : "bạn"} · {formatTime(l.created_at)}</span>
          </div>
          <p className="text-slate-300">{l.lesson}</p>
          {l.review_status === "proposed" && (
            <div className="flex gap-2">
              <SecondaryButton disabled={review.isPending} onClick={() => review.mutate({ id: l.id, decision: "approve" })}>Duyệt → tri thức</SecondaryButton>
              <SecondaryButton disabled={review.isPending} onClick={() => review.mutate({ id: l.id, decision: "reject" })}>Từ chối</SecondaryButton>
            </div>
          )}
        </div>
      ))}
      {review.isError && <ErrorView error={review.error} />}
      <form className="space-y-2 max-w-lg" onSubmit={(e) => { e.preventDefault(); propose.mutate({ title, lesson: text }, { onSuccess: () => { setTitle(""); setText(""); } }); }}>
        <h3 className="text-sm font-medium">Đề xuất bài học</h3>
        <input className={inputClass} placeholder="Tiêu đề" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea className={inputClass} rows={2} placeholder="Bài học" value={text} onChange={(e) => setText(e.target.value)} />
        <SecondaryButton type="submit" disabled={propose.isPending || !title.trim() || !text.trim()}>Gửi đề xuất</SecondaryButton>
        {propose.isError && <ErrorView error={propose.error} />}
      </form>
    </div>
  );
}

function ProposalsTab({ companyId }: { companyId: string }) {
  const proposals = useRoleProposals(companyId);
  const review = useReviewRoleProposal(companyId);
  const agents = useAgents(companyId);
  const depts = useDepartments(companyId);
  const agentName = (id: unknown) => agents.data?.find((a) => a.id === id)?.name ?? "—";
  const describe = (p: RoleProposal) =>
    Object.entries(p.changes_json).map(([k, v]) => {
      if (k === "reports_to_agent_id") return `Báo cáo cho: ${v ? agentName(v) : "không ai"}`;
      if (k === "department_id") return `Phòng ban: ${depts.data?.find((d) => d.id === v)?.name ?? "không thuộc phòng ban"}`;
      if (k === "role") return `Vai trò: ${v}`;
      if (k === "instructions") return `Chỉ dẫn mới (tạo version mới): ${v}`;
      return `${k}: ${String(v)}`;
    });
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-400">Agent chỉ được đề xuất. Duyệt sẽ áp dụng qua cùng kiểm tra hợp lệ như khi bạn sửa tay (ví dụ chặn vòng lặp báo cáo).</p>
      {proposals.isLoading && <Loading />}
      {proposals.data?.length === 0 && <Empty>Chưa có đề xuất.</Empty>}
      {proposals.data?.map((p) => (
        <div key={p.id} className="p-3 rounded border border-slate-800 text-sm space-y-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={p.status} />
            <b>{agentName(p.agent_id)}</b>
            <span className="text-xs text-slate-500 ml-auto">đề xuất bởi {p.proposed_by.startsWith("agent:") ? agentName(p.proposed_by.slice(6)) : "bạn"}</span>
          </div>
          <ul className="list-disc pl-5 text-slate-300">
            {describe(p).map((d) => <li key={d}>{d}</li>)}
          </ul>
          {p.rationale && <p className="text-xs text-slate-400">Lý do: {p.rationale}</p>}
          {p.status === "proposed" && (
            <div className="flex gap-2">
              <SecondaryButton disabled={review.isPending} onClick={() => review.mutate({ id: p.id, decision: "approve" })}>Duyệt và áp dụng</SecondaryButton>
              <SecondaryButton disabled={review.isPending} onClick={() => review.mutate({ id: p.id, decision: "reject" })}>Từ chối</SecondaryButton>
            </div>
          )}
        </div>
      ))}
      {review.isError && <ErrorView error={review.error} />}
    </div>
  );
}
