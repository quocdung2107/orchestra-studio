import type { ButtonHTMLAttributes, ReactNode } from "react";
import { errorMessage } from "../api/client";

export function Loading({ label = "Đang tải…" }: { label?: string }) {
  return <p className="p-4 text-sm text-slate-400" role="status">{label}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="p-6 text-sm text-slate-400 border border-dashed border-slate-700 rounded">{children}</div>;
}

export function ErrorView({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="p-3 text-sm rounded border border-red-800 bg-red-950/50 text-red-200">
      <p>Lỗi: {errorMessage(error)}</p>
      {onRetry && (
        <button className="mt-2 underline" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-900 text-emerald-200",
  completed: "bg-emerald-900 text-emerald-200",
  running: "bg-sky-900 text-sky-200",
  in_progress: "bg-sky-900 text-sky-200",
  queued: "bg-slate-700 text-slate-200",
  pending: "bg-slate-700 text-slate-200",
  draft: "bg-slate-700 text-slate-200",
  inactive: "bg-amber-900 text-amber-200",
  failed: "bg-red-900 text-red-200",
  archived: "bg-slate-800 text-slate-400",
  waiting_approval: "bg-amber-900 text-amber-200",
  paused: "bg-amber-900 text-amber-200",
  cancel_requested: "bg-slate-700 text-slate-300",
  cancelled: "bg-slate-800 text-slate-400",
  proposed: "bg-amber-900 text-amber-200",
  approved: "bg-emerald-900 text-emerald-200",
  rejected: "bg-red-900 text-red-200",
  expired: "bg-slate-800 text-slate-400",
  producing: "bg-sky-900 text-sky-200",
  ready: "bg-emerald-900 text-emerald-200",
  succeeded: "bg-emerald-900 text-emerald-200",
  qa_failed: "bg-amber-900 text-amber-200",
};

const STATUS_TEXT: Record<string, string> = {
  waiting_approval: "chờ duyệt",
  paused: "tạm dừng",
  cancel_requested: "đang hủy",
  cancelled: "đã hủy",
  proposed: "chờ duyệt",
  approved: "đã duyệt",
  rejected: "từ chối",
  expired: "hết hạn",
  producing: "đang sản xuất",
  ready: "sẵn sàng",
  qa_failed: "QA chưa đạt",
  succeeded: "xong",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[status] ?? "bg-slate-700"}`}>
      {STATUS_TEXT[status] ?? status}
    </span>
  );
}

export function Button({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`px-3 py-1.5 rounded text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      {...props}
    />
  );
}

export function SecondaryButton({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`px-3 py-1.5 rounded text-sm border border-slate-600 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      {...props}
    />
  );
}

export function Section({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

export const inputClass =
  "w-full px-2 py-1.5 rounded bg-slate-900 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500";
