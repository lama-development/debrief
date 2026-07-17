import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus, X } from "lucide-react";
import { toast } from "sonner";

import { AppHeader } from "@/components/AppHeader";
import { ChatPanel } from "@/components/ChatPanel";
import { ResolveDialog } from "@/components/ResolveDialog";
import { SeverityBadge } from "@/components/SeverityBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { SEVERITY_CLASS, SEVERITY_TOOLTIP } from "@/lib/labels";
import { useIncident, useReopenIncident } from "@/hooks/useIncident";
import { useIncidentInvalidation } from "@/hooks/useIncidentInvalidation";
import { useTeams } from "@/hooks/useTeams";
import { useUpdateClassification } from "@/hooks/useUpdateClassification";
import { ApiError } from "@/lib/api";
import type { DebriefReport, Severity } from "@/lib/types";

const ALL_SEVERITIES: Severity[] = ["SEV1", "SEV2", "SEV3", "SEV4"];

function SeverityDropdown({
  value,
  disabled,
  onChange,
}: {
  value: Severity;
  disabled: boolean;
  onChange: (s: Severity) => void;
}) {
  return (
    <Select
      value={value}
      options={ALL_SEVERITIES.map((severity) => ({
        value: severity,
        label: severity,
        title: SEVERITY_TOOLTIP[severity],
      }))}
      onChange={onChange}
      disabled={disabled}
      ariaLabel="Cambia severità"
      className="w-fit"
      triggerClassName={cn(
        "h-auto w-auto gap-1 rounded-full px-2.5 py-0.5 font-semibold shadow-sm",
        SEVERITY_CLASS[value],
      )}
      menuClassName="min-w-[96px]"
      showCheck={false}
    />
  );
}

export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const invalidateIncident = useIncidentInvalidation(id);
  const { data: incident, isLoading, isError } = useIncident(id);
  const { teams, teamName } = useTeams();
  const reopen = useReopenIncident(id);
  const updateClass = useUpdateClassification(id);
  const [mobileTab, setMobileTab] = useState<"chat" | "details">("chat");
  const [showTeamPicker, setShowTeamPicker] = useState(false);
  const teamPickerRef = useRef<HTMLDivElement>(null);

  // Chiude il selettore dei team quando il clic avviene fuori dal pannello.
  useEffect(() => {
    if (!showTeamPicker) return;
    function onPointerDown(e: PointerEvent) {
      if (teamPickerRef.current && !teamPickerRef.current.contains(e.target as Node)) {
        setShowTeamPicker(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [showTeamPicker]);

  if (isLoading) {
    return (
      <Shell>
        <p className="text-muted-foreground">Caricamento incidente…</p>
      </Shell>
    );
  }
  if (isError || !incident) {
    return (
      <Shell>
        <p className="text-destructive">Incidente non trovato.</p>
        <Link to="/" className="text-sm text-primary hover:underline">
          ← Torna alla dashboard
        </Link>
      </Shell>
    );
  }

  async function onReopen() {
    try {
      await reopen.mutateAsync();
      toast.success("Incidente riaperto");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Riapertura fallita");
    }
  }

  const isResolved = incident.status === "resolved";
  const currentSeverity = incident.severity;

  async function onSeverityChange(newSev: Severity) {
    if (newSev === currentSeverity) return;
    try {
      await updateClass.mutateAsync({ severity: newSev });
      toast.success(`Severità aggiornata a ${newSev}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aggiornamento fallito");
    }
  }

  async function onAddTeam(teamId: string) {
    try {
      await updateClass.mutateAsync({ add_teams: [teamId] });
      setShowTeamPicker(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aggiornamento fallito");
    }
  }

  async function onRemoveTeam(teamId: string) {
    try {
      await updateClass.mutateAsync({ remove_teams: [teamId] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rimozione fallita");
    }
  }

  return (
    <div className="flex h-svh flex-col bg-muted/30">
      <AppHeader />

      {/* Intestazione incidente */}
      <div className="container relative z-20 pt-2 sm:pt-4">
        <Card className="px-3 py-3 sm:px-4">
          <div className="flex min-w-0 items-start gap-2 sm:items-center sm:gap-3">
            <Button
              asChild
              variant="ghost"
              size="icon"
              className="-ml-1 h-9 w-9 shrink-0 sm:ml-0 sm:h-10 sm:w-10"
              aria-label="Torna alla dashboard"
            >
              <Link to="/">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-base font-semibold leading-tight tracking-tight">
                {incident.title}
              </h1>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 sm:mt-1.5 sm:flex-nowrap">
                <div className="flex min-w-0 items-center gap-2">
                  <StatusBadge status={incident.status} />
                  {!isResolved && incident.severity ? (
                    <SeverityDropdown
                      value={incident.severity}
                      disabled={updateClass.isPending}
                      onChange={(s) => void onSeverityChange(s)}
                    />
                  ) : (
                    <SeverityBadge severity={incident.severity} />
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2 sm:hidden">
                  {!isResolved && <ResolveDialog incidentId={incident.id} triggerSize="sm" />}
                  {isResolved && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={onReopen}
                      disabled={reopen.isPending}
                    >
                      Riapri
                    </Button>
                  )}
                </div>
              </div>
            </div>
            <div className="hidden shrink-0 items-center gap-2 sm:flex">
              {!isResolved && <ResolveDialog incidentId={incident.id} />}
              {isResolved && (
                <Button variant="outline" onClick={onReopen} disabled={reopen.isPending}>
                  Riapri
                </Button>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Due pannelli: dettaglio (sinistra) + chat (destra) */}
      <div className="container flex min-h-0 flex-1 flex-col gap-2 py-2 sm:gap-4 sm:py-4">
        {/* Selettore scheda — visibile solo sotto lg */}
        <div className="flex rounded-lg bg-muted p-1 text-sm font-medium lg:hidden">
          <button
            type="button"
            onClick={() => setMobileTab("chat")}
            className={cn(
              "flex-1 rounded-md py-1.5 transition-colors",
              mobileTab === "chat"
                ? "bg-background shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Chat
          </button>
          <button
            type="button"
            onClick={() => setMobileTab("details")}
            className={cn(
              "flex-1 rounded-md py-1.5 transition-colors",
              mobileTab === "details"
                ? "bg-background shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Dettagli
          </button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 sm:gap-4 lg:grid-cols-[2fr_3fr]">
          {/* Sinistra: descrizione, timeline e debriefing */}
          <div
            className={cn(
              "min-h-0 space-y-4 overflow-y-auto pr-1",
              mobileTab !== "details" && "hidden lg:block",
            )}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Descrizione</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm text-foreground/90">
                  {incident.description}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Partecipanti</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {incident.participants.map((participant) => (
                    <span
                      key={participant.id}
                      className="rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium"
                    >
                      {participant.username}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Riquadro dei team — modificabile finché l'incidente non è risolto */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Team coinvolti</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {incident.involved_teams.map((teamId) => {
                    const label = teamName(teamId);
                    return (
                      <span
                        key={teamId}
                        className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2.5 py-0.5 text-xs font-medium"
                      >
                        {label}
                        {!isResolved && (
                          <button
                            type="button"
                            onClick={() => void onRemoveTeam(teamId)}
                            disabled={updateClass.isPending}
                            aria-label={`Rimuovi ${label}`}
                            className="ml-0.5 rounded-full hover:text-destructive disabled:opacity-50"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </span>
                    );
                  })}

                  {!isResolved && (
                    <div ref={teamPickerRef} className="contents">
                      {!showTeamPicker ? (
                        <button
                          type="button"
                          onClick={() => setShowTeamPicker(true)}
                          className="inline-flex items-center gap-1 rounded-full border border-dashed px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground"
                        >
                          <Plus className="h-3 w-3" />
                          Aggiungi
                        </button>
                      ) : (
                        teams
                          .filter((t) => !incident.involved_teams.includes(t.id))
                          .map((t) => (
                            <button
                              key={t.id}
                              type="button"
                              onClick={() => void onAddTeam(t.id)}
                              disabled={updateClass.isPending}
                              className="inline-flex items-center gap-1 rounded-full border border-dashed px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:border-foreground/40 hover:text-foreground disabled:opacity-50"
                            >
                              <Plus className="h-3 w-3" />
                              {t.name}
                            </button>
                          ))
                      )}
                    </div>
                  )}

                  {incident.involved_teams.length === 0 && isResolved && (
                    <p className="text-xs text-muted-foreground">Nessun team coinvolto.</p>
                  )}
                </div>
              </CardContent>
            </Card>

            {incident.debrief_report && <DebriefReportCard report={incident.debrief_report} />}

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <Timeline events={incident.timeline} />
              </CardContent>
            </Card>
          </div>

          {/* Destra: chat */}
          <Card
            className={cn(
              "-mx-4 flex min-h-0 flex-col overflow-hidden rounded-none border-x-0 sm:mx-0 sm:rounded-lg sm:border-x",
              mobileTab !== "chat" && "hidden lg:flex",
            )}
          >
            <CardContent className="min-h-0 flex-1 p-0">
              <ChatPanel
                key={incident.id}
                incidentId={incident.id}
                status={incident.status}
                isSeedIncident={incident.created_by === null}
                initialEvents={incident.timeline}
                initialDraft={incident.status === "open" ? incident.description : ""}
                onIncidentChanged={invalidateIncident}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DebriefReportCard({ report }: { report: DebriefReport }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Debriefing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">{report.resolution}</CardContent>
    </Card>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-muted/30">
      <AppHeader />
      <main className="container space-y-2 py-6">{children}</main>
    </div>
  );
}
