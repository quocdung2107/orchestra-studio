import { useState } from "react";
import { useCreateCompany } from "../api/hooks";
import { useInstantiateTemplate, useTemplates } from "../api/hooks-p1";
import { useSelection } from "../state/selection";
import { Button, ErrorView, SecondaryButton, inputClass } from "../components/ui";

export function NoCompany() {
  const { setCompanyId, setView } = useSelection();
  const create = useCreateCompany();
  const templates = useTemplates();
  const inst = useInstantiateTemplate();
  const [tplName, setTplName] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <div className="max-w-lg space-y-8">
      <div>
        <h1 className="text-xl font-semibold mb-1">Bắt đầu</h1>
        <p className="text-sm text-slate-400">Chọn company ở thanh bên, tạo mới, hoặc tạo tổ chức mẫu.</p>
      </div>
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            { name, description },
            { onSuccess: (c) => { setCompanyId(c.id); setView("overview"); setName(""); setDescription(""); } },
          );
        }}
      >
        <h2 className="font-medium">Tạo company</h2>
        <input className={inputClass} placeholder="Tên company" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea className={inputClass} placeholder="Mô tả (không bắt buộc)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <Button type="submit" disabled={create.isPending || !name.trim()}>
          {create.isPending ? "Đang tạo…" : "Tạo company"}
        </Button>
        {create.isError && <ErrorView error={create.error} />}
      </form>
      <div className="space-y-2">
        <h2 className="font-medium">Tạo từ template</h2>
        <p className="text-sm text-slate-400">Template là file YAML trong thư mục templates/company. Agent chạy bằng Mock Runtime, không gọi AI.</p>
        <input className={inputClass} placeholder="Tên company (để trống = theo template)" value={tplName} onChange={(e) => setTplName(e.target.value)} />
        {templates.data
          ?.filter((t) => t.kind === "company")
          .map((t) => (
            <div key={t.id} className="border border-slate-800 rounded p-3">
              <div className="font-medium">{t.title}</div>
              <p className="text-sm text-slate-400 mb-2">{t.description}</p>
              <SecondaryButton
                disabled={inst.isPending}
                onClick={() => inst.mutate({ id: t.id, name: tplName.trim() || undefined }, { onSuccess: (c) => { setCompanyId(c.id); setView("organization"); setTplName(""); } })}
              >
                {inst.isPending ? "Đang tạo…" : `Tạo từ “${t.title}”`}
              </SecondaryButton>
            </div>
          ))}
        {templates.isError && <ErrorView error={templates.error} />}
        {inst.isError && <ErrorView error={inst.error} />}
      </div>
    </div>
  );
}
