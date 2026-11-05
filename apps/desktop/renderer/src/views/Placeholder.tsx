import type { View } from "../state/selection";

const INFO: Partial<Record<View, string>> = {
  organization: "Sơ đồ tổ chức dạng graph sẽ có ở P1.",
  approvals: "Phê duyệt hành động sẽ có ở P2.",
  knowledge: "Tri thức và bài học sẽ có ở P3.",
  analytics: "KPI và phân tích sẽ có ở P4.",
};

export function Placeholder({ view }: { view: View }) {
  return (
    <div className="text-slate-400">
      <h1 className="text-xl font-semibold text-slate-200 mb-2">Chưa có</h1>
      <p>{INFO[view]}</p>
      <p className="mt-2 text-sm">Màn hình này cố ý để trống thay vì hiển thị dữ liệu giả.</p>
    </div>
  );
}
