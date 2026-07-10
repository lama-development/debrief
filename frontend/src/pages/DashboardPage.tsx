import { useState } from "react";
import { Info } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { AppHeader } from "@/components/AppHeader";
import { NewIncidentDialog } from "@/components/NewIncidentDialog";
import { SeverityBadge } from "@/components/SeverityBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { useIncidents } from "@/hooks/useIncidents";
import { useMetrics } from "@/hooks/useMetrics";
import { ALL_STATUSES, STATUS_LABEL, formatDateTime, formatMttr } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { IncidentStatus } from "@/lib/types";

const OPEN_STATUSES: IncidentStatus[] = ["open", "active"];

// Classi base per le celle della tabella (intestazione e corpo).
const TH = "h-12 px-4 text-left align-middle font-medium text-muted-foreground";
const TD = "p-4 align-middle";

function StatCard({
  title,
  value,
  description,
}: {
  title: string;
  value: string | number;
  description: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          {title}
          <Tooltip content={description}>
            <Info className="size-3.5 cursor-help" aria-hidden="true" />
          </Tooltip>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const [filter, setFilter] = useState<IncidentStatus | undefined>(undefined);
  const navigate = useNavigate();
  const metrics = useMetrics();
  const incidents = useIncidents(filter);

  const byStatus = metrics.data?.by_status ?? {};
  const openCount = OPEN_STATUSES.reduce((sum, s) => sum + (byStatus[s] ?? 0), 0);
  const resolvedCount = byStatus["resolved"] ?? 0;

  return (
    <div className="min-h-screen bg-muted/30">
      <AppHeader />
      <main className="container space-y-6 py-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Dashboard</h1>
          <NewIncidentDialog />
        </div>

        {/* Metriche */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)
          ) : (
            <>
              <StatCard
                title="Incidenti assegnati"
                value={metrics.data?.total ?? 0}
                description="Incidenti creati da te, a cui partecipi o assegnati al tuo team."
              />
              <StatCard
                title="In corso"
                value={openCount}
                description="Incidenti aperti o attualmente in gestione."
              />
              <StatCard
                title="Risolti"
                value={resolvedCount}
                description="Incidenti che sono stati contrassegnati come risolti."
              />
              <StatCard
                title="MTTR medio"
                value={formatMttr(metrics.data?.mttr_seconds ?? null)}
                description="Tempo medio impiegato per risolvere un incidente (Mean Time To Resolution)."
              />
            </>
          )}
        </div>

        {/* Filtro per stato */}
        <div className="flex gap-2 overflow-x-auto pb-0.5 sm:flex-wrap sm:overflow-visible [&>*]:shrink-0">
          <FilterChip
            label="Tutti"
            active={filter === undefined}
            onClick={() => setFilter(undefined)}
          />
          {ALL_STATUSES.map((s) => (
            <FilterChip
              key={s}
              label={STATUS_LABEL[s]}
              active={filter === s}
              onClick={() => setFilter(s)}
            />
          ))}
        </div>

        {/* Tabella incidenti */}
        <Card>
          <CardContent className="p-0">
            <div className="w-full overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className={cn(TH, "hidden w-28 sm:table-cell")}>ID</th>
                    <th className={TH}>Titolo</th>
                    <th className={cn(TH, "hidden w-40 md:table-cell")}>Severità</th>
                    <th className={cn(TH, "w-36")}>Stato</th>
                    <th className={cn(TH, "hidden w-40 md:table-cell")}>Creato</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.isLoading && (
                    <tr className="border-b last:border-b-0">
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">
                        Caricamento…
                      </td>
                    </tr>
                  )}
                  {incidents.isError && (
                    <tr className="border-b last:border-b-0">
                      <td colSpan={5} className="py-8 text-center text-destructive">
                        Errore nel caricamento degli incidenti.
                      </td>
                    </tr>
                  )}
                  {incidents.data?.length === 0 && (
                    <tr className="border-b last:border-b-0">
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">
                        Nessun incidente{filter ? " in questo stato" : ""}.
                      </td>
                    </tr>
                  )}
                  {incidents.data?.map((inc) => (
                    <tr
                      key={inc.id}
                      className="cursor-pointer border-b last:border-b-0 hover:bg-muted/50"
                      onClick={() => navigate(`/incidents/${inc.id}`)}
                    >
                      <td className={cn(TD, "hidden font-mono text-sm sm:table-cell")}>{inc.id}</td>
                      <td className={cn(TD, "font-medium")}>{inc.title}</td>
                      <td className={cn(TD, "hidden md:table-cell")}>
                        <SeverityBadge severity={inc.severity} />
                      </td>
                      <td className={TD}>
                        <StatusBadge status={inc.status} />
                      </td>
                      <td className={cn(TD, "hidden text-sm text-muted-foreground md:table-cell")}>
                        {formatDateTime(inc.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-sm font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground shadow-sm"
          : "border-border bg-secondary/70 text-secondary-foreground hover:bg-secondary dark:bg-secondary/60 dark:hover:bg-secondary/80",
      )}
    >
      {label}
    </button>
  );
}
