import { useState } from "react";
import { useCreateCompany, useSeedDemo } from "../api/hooks";
import { useSelection } from "../state/selection";
import { Button, ErrorView, SecondaryButton, inputClass } from "../components/ui";

export function NoCompany() {
  const { setCompanyId, setView } = useSelection();
  const create = useCreateCompany();
  const seed = useSeedDemo();
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
        <h2 className="font-medium">Tổ chức mẫu</h2>
        <p className="text-sm text-slate-400">
          Demo Video Studio: 8 agent (CEO, CMO, Researcher, Strategist, Producer, Scriptwriter, Reviewer, Secretary) chạy bằng Mock Runtime, không gọi AI.
        </p>
        <SecondaryButton
          disabled={seed.isPending}
          onClick={() => seed.mutate(undefined, { onSuccess: (c) => { setCompanyId(c.id); setView("runs"); } })}
        >
          {seed.isPending ? "Đang tạo…" : "Tạo Demo Video Studio"}
        </SecondaryButton>
        {seed.isError && <ErrorView error={seed.error} />}
      </div>
    </div>
  );
}
