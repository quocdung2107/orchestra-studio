import { useEffect, useState } from "react";
import { useCompanies, useHealth } from "./api/hooks";
import { ActivityConsole } from "./components/ActivityConsole";
import { Inspector } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { ErrorView, Loading } from "./components/ui";
import { useEventStream } from "./live/useEventStream";
import { SelectionProvider, useSelection } from "./state/selection";
import { AgentsView } from "./views/AgentsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { KnowledgeView } from "./views/KnowledgeView";
import { ConnectionsView } from "./views/ConnectionsView";
import { KpiView } from "./views/KpiView";
import { BackupView } from "./views/BackupView";
import { WorkersView } from "./views/WorkersView";
import { CapabilitiesView } from "./views/CapabilitiesView";
import { OrgView } from "./views/OrgView";
import { CompanyOverview } from "./views/CompanyOverview";
import { NoCompany } from "./views/NoCompany";
import { Placeholder } from "./views/Placeholder";
import { RunsView } from "./views/RunsView";
import { MediaSettingsView } from "./views/MediaSettingsView";
import { ProductionView } from "./views/ProductionView";

export function App() {
  return (
    <SelectionProvider>
      <Shell />
    </SelectionProvider>
  );
}

function Shell() {
  const { companyId, setCompanyId, view, selection } = useSelection();
  const health = useHealth();
  const companies = useCompanies();
  const stream = useEventStream(companyId);
  const [consoleOpen, setConsoleOpen] = useState(true);

  // Drop a remembered company that no longer exists.
  useEffect(() => {
    if (companies.data && companyId && !companies.data.some((c) => c.id === companyId)) {
      setCompanyId(null);
    }
  }, [companies.data, companyId, setCompanyId]);

  if (health.isError) {
    return (
      <div className="p-8 max-w-lg">
        <h1 className="text-lg font-semibold mb-2">Orchestra Studio</h1>
        <ErrorView error={health.error} onRetry={() => health.refetch()} />
        <p className="mt-3 text-sm text-slate-400">
          Hãy chạy backend: <code>pnpm backend</code> (xem README).
        </p>
      </div>
    );
  }
  if (health.isLoading || companies.isLoading) return <Loading label="Đang kết nối backend…" />;
  if (companies.isError) return <ErrorView error={companies.error} onRetry={() => companies.refetch()} />;

  return (
    <div className="h-full grid grid-cols-[220px_1fr_auto] grid-rows-[1fr_auto]">
      <Sidebar companies={companies.data ?? []} />
      <main className="overflow-auto p-6">
        {!companyId ? (
          <NoCompany />
        ) : view === "overview" ? (
          <CompanyOverview companyId={companyId} />
        ) : view === "production" ? (
          <ProductionView companyId={companyId} />
        ) : view === "media_settings" ? (
          <MediaSettingsView companyId={companyId} />
        ) : view === "agents" ? (
          <AgentsView companyId={companyId} />
        ) : view === "runs" ? (
          <RunsView companyId={companyId} />
        ) : view === "organization" ? (
          <OrgView companyId={companyId} />
        ) : view === "capabilities" ? (
          <CapabilitiesView companyId={companyId} />
        ) : view === "approvals" ? (
          <ApprovalsView companyId={companyId} />
        ) : view === "knowledge" ? (
          <KnowledgeView companyId={companyId} />
        ) : view === "analytics" ? (
          <KpiView companyId={companyId} />
        ) : view === "connections" ? (
          <ConnectionsView companyId={companyId} />
        ) : view === "workers" ? (
          <WorkersView />
        ) : view === "backups" ? (
          <BackupView />
        ) : (
          <Placeholder view={view} />
        )}
      </main>
      <Inspector companyId={companyId} selection={selection} />
      <div className="col-span-3">
        <ActivityConsole
          events={stream.events}
          status={stream.status}
          open={consoleOpen}
          onToggle={() => setConsoleOpen((o) => !o)}
        />
      </div>
    </div>
  );
}
