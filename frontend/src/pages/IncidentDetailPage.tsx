import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, ChevronDown, Plus, X } from "lucide-react"
import { toast } from "sonner"

import { AppHeader } from "@/components/AppHeader"
import { ChatPanel } from "@/components/ChatPanel"
import { ResolveDialog } from "@/components/ResolveDialog"
import { SeverityBadge } from "@/components/SeverityBadge"
import { StatusBadge } from "@/components/StatusBadge"
import { Timeline } from "@/components/Timeline"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { SEVERITY_CLASS, SEVERITY_TOOLTIP } from "@/lib/labels"
import { useIncident, useReopenIncident } from "@/hooks/useIncident"
import { useUpdateClassification } from "@/hooks/useUpdateClassification"
import { ApiError } from "@/lib/api"
import type { IncidentStatus, DebriefReport, Severity } from "@/lib/types"

const ALL_SEVERITIES: Severity[] = ["SEV1", "SEV2", "SEV3", "SEV4"]

function SeverityDropdown({
  value,
  disabled,
  onChange,
}: {
  value: Severity
  disabled: boolean
  onChange: (s: Severity) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        aria-label="Cambia severità"
        title={SEVERITY_TOOLTIP[value]}
        className={cn(
          "inline-flex cursor-pointer items-center gap-1 rounded-full border px-2.5 py-0.5 text-sm font-semibold shadow-sm disabled:opacity-50",
          SEVERITY_CLASS[value],
        )}
      >
        {value}
        <ChevronDown className="h-3 w-3 opacity-70" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[80px] rounded-md border bg-background p-1 shadow-md">
          {ALL_SEVERITIES.map((s) => (
            <button
              key={s}
              type="button"
              disabled={disabled}
              onClick={() => { onChange(s); setOpen(false) }}
              title={SEVERITY_TOOLTIP[s]}
              className={cn(
                "w-full rounded px-2 py-1.5 text-left text-sm disabled:opacity-50",
                s === value ? "font-semibold text-foreground" : "hover:bg-muted",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// Team catalog mirrored from seed/teams.json — IDs stabili, non cambiano a runtime.
const ALL_TEAMS: { id: string; label: string }[] = [
  { id: "IT_INTERNAL", label: "IT Interno" },
  { id: "IT_DEV", label: "Sviluppatori Genius" },
  { id: "IT_EXTERNAL", label: "2000net Srl" },
  { id: "PLC_VENDOR", label: "Fornitore PLC" },
  { id: "PRODUCTION", label: "Reparto Produzione" },
  { id: "LAB", label: "Laboratorio" },
  { id: "MANAGEMENT", label: "Direzione" },
]

const RESOLVABLE: IncidentStatus[] = ["open", "active"]

export function IncidentDetailPage() {
  const { id = "" } = useParams()
  const qc = useQueryClient()
  const { data: incident, isLoading, isError } = useIncident(id)
  const reopen = useReopenIncident(id)
  const updateClass = useUpdateClassification(id)
  const [mobileTab, setMobileTab] = useState<"chat" | "details">("chat")
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const teamPickerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showTeamPicker) return
    function onPointerDown(e: PointerEvent) {
      if (teamPickerRef.current && !teamPickerRef.current.contains(e.target as Node)) {
        setShowTeamPicker(false)
      }
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [showTeamPicker])

  if (isLoading) {
    return (
      <Shell>
        <p className="text-muted-foreground">Caricamento incidente…</p>
      </Shell>
    )
  }
  if (isError || !incident) {
    return (
      <Shell>
        <p className="text-destructive">Incidente non trovato.</p>
        <Link to="/" className="text-sm text-primary hover:underline">
          ← Torna alla dashboard
        </Link>
      </Shell>
    )
  }

  async function onReopen() {
    try {
      await reopen.mutateAsync()
      toast.success("Incidente riaperto")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Riapertura fallita")
    }
  }

  const canResolve = RESOLVABLE.includes(incident.status)
  const isResolved = incident.status === "resolved"
  const canOverride = !isResolved
  const currentSeverity = incident.severity

  async function onSeverityChange(newSev: Severity) {
    if (newSev === currentSeverity) return
    try {
      await updateClass.mutateAsync({ severity: newSev })
      toast.success(`Severità aggiornata a ${newSev}`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aggiornamento fallito")
    }
  }

  async function onAddTeam(teamId: string) {
    try {
      await updateClass.mutateAsync({ add_teams: [teamId] })
      setShowTeamPicker(false)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aggiornamento fallito")
    }
  }

  async function onRemoveTeam(teamId: string) {
    try {
      await updateClass.mutateAsync({ remove_teams: [teamId] })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rimozione fallita")
    }
  }

  return (
    <div className="flex h-svh flex-col bg-muted/30">
      <AppHeader />

      {/* Intestazione incidente */}
      <div className="container pt-4 relative z-20">
        <Card className="px-4 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <Button asChild variant="ghost" size="icon" className="shrink-0" aria-label="Torna alla dashboard">
              <Link to="/">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div className="min-w-0 flex-1">
              <h1 className="text-base font-semibold tracking-tight leading-tight line-clamp-2">{incident.title}</h1>
              <div className="flex items-center justify-between gap-2 mt-1.5">
                <div className="flex items-center gap-2">
                  <StatusBadge status={incident.status} />
                  {canOverride && incident.severity ? (
                    <SeverityDropdown
                      value={incident.severity}
                      disabled={updateClass.isPending}
                      onChange={(s) => void onSeverityChange(s)}
                    />
                  ) : (
                    <SeverityBadge severity={incident.severity} />
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0 sm:hidden">
                  {canResolve && <ResolveDialog incidentId={incident.id} />}
                  {isResolved && (
                    <Button variant="outline" size="sm" onClick={onReopen} disabled={reopen.isPending}>
                      Riapri
                    </Button>
                  )}
                </div>
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-2 shrink-0">
              {canResolve && <ResolveDialog incidentId={incident.id} />}
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
      <div className="container min-h-0 flex-1 flex flex-col gap-4 py-4">
        {/* Selettore tab — visibile solo sotto lg */}
        <div className="flex rounded-lg bg-muted p-1 text-sm font-medium lg:hidden">
          <button
            type="button"
            onClick={() => setMobileTab("chat")}
            className={cn(
              "flex-1 rounded-md py-1.5 transition-colors",
              mobileTab === "chat" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            Chat
          </button>
          <button
            type="button"
            onClick={() => setMobileTab("details")}
            className={cn(
              "flex-1 rounded-md py-1.5 transition-colors",
              mobileTab === "details" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            Dettagli
          </button>
        </div>

        <div className="min-h-0 flex-1 grid grid-cols-1 gap-4 lg:grid-cols-[2fr_3fr]">
          {/* Sinistra: descrizione, timeline e debriefing */}
          <div className={cn("min-h-0 space-y-4 overflow-y-auto pr-1", mobileTab !== "details" && "hidden lg:block")}>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Descrizione</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm text-foreground/90">{incident.description}</p>
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
                      className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium"
                    >
                      {participant.username}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Card team coinvolti — visibile sempre, modificabile se non risolto */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Team coinvolti</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {incident.involved_teams.map((teamId) => {
                    const label = ALL_TEAMS.find((t) => t.id === teamId)?.label ?? teamId
                    return (
                      <span
                        key={teamId}
                        className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium"
                      >
                        {label}
                        {canOverride && (
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
                    )
                  })}

                  {canOverride && (
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
                        ALL_TEAMS.filter((t) => !incident.involved_teams.includes(t.id)).map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => void onAddTeam(t.id)}
                            disabled={updateClass.isPending}
                            className="inline-flex items-center gap-1 rounded-full border border-dashed px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-foreground/40 disabled:opacity-50"
                          >
                            <Plus className="h-3 w-3" />
                            {t.label}
                          </button>
                        ))
                      )}
                    </div>
                  )}

                  {incident.involved_teams.length === 0 && !canOverride && (
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
          <Card className={cn("flex min-h-0 flex-col overflow-hidden", mobileTab !== "chat" && "hidden lg:flex")}>
            <CardContent className="min-h-0 flex-1 p-0">
              <ChatPanel
                key={incident.id}
                incidentId={incident.id}
                status={incident.status}
                initialEvents={incident.timeline}
                initialDraft={incident.status === "open" ? incident.description : ""}
                onTurnComplete={() => qc.invalidateQueries({ queryKey: ["incident", incident.id] })}
                onClassificationChanged={() => qc.invalidateQueries({ queryKey: ["incident", incident.id] })}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function DebriefReportCard({ report }: { report: DebriefReport }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Debriefing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {report.resolution && <Field label="Risoluzione" value={report.resolution} />}
      </CardContent>
    </Card>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <p className="whitespace-pre-wrap">{value}</p>
    </div>
  )
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-muted/30">
      <AppHeader />
      <main className="container space-y-2 py-6">{children}</main>
    </div>
  )
}
