import { useBackups, useCreateBackup } from "../api/hooks-p5";
import { Button, Empty, ErrorView, Loading, Section, formatTime } from "../components/ui";
import { formatBytes } from "./ConnectionsView";

/** Backups of all local data (ADR-0027). Never contains secrets; restore runs from the CLI. */
export function BackupView() {
  const list = useBackups();
  const create = useCreateBackup();
  if (list.isLoading) return <Loading />;
  if (list.isError) return <ErrorView error={list.error} onRetry={() => list.refetch()} />;
  const data = list.data!;
  return (
    <div className="max-w-3xl">
      <Section
        title="Sao lưu dữ liệu"
        actions={
          <Button disabled={create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Đang sao lưu…" : "Tạo bản sao lưu"}
          </Button>
        }
      >
        <p className="text-sm text-slate-400 mb-3">
          Gồm cơ sở dữ liệu (mọi company), artifact và workspace, nén thành một file zip trong{" "}
          <code className="text-slate-300">{data.directory}</code>. Không chứa API key (key nằm trong Windows Credential
          Manager).
        </p>
        {create.isError && <ErrorView error={create.error} />}
        {create.isSuccess && <p className="text-sm text-emerald-300 mb-2">Đã tạo {create.data.name}</p>}
        {data.items.length === 0 ? (
          <Empty>Chưa có bản sao lưu nào.</Empty>
        ) : (
          <ul className="divide-y divide-slate-800 text-sm" data-testid="backup-list">
            {data.items.map((b) => (
              <li key={b.name} className="py-2 flex justify-between gap-4">
                <span className="font-mono text-xs break-all">{b.name}</span>
                <span className="text-slate-400 whitespace-nowrap">
                  {formatTime(b.created_at)} · {formatBytes(b.size_bytes)}
                  {b.files == null ? " · không đọc được" : ` · ${b.files} file`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="Khôi phục">
        <p className="text-sm text-slate-400">
          Khôi phục thay toàn bộ dữ liệu hiện tại, nên chỉ làm khi app đã tắt. Đóng app, rồi chạy trong thư mục dự án:
        </p>
        <pre className="mt-2 bg-slate-900 border border-slate-800 rounded p-2 text-xs">{data.restore_command}</pre>
        <p className="text-xs text-slate-500 mt-2">
          Lệnh kiểm tra checksum trước khi ghi, và giữ dữ liệu cũ trong <code>data/pre-restore-…</code>.
        </p>
      </Section>
    </div>
  );
}
