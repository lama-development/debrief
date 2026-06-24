import type { ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowLeft } from "lucide-react"
import { toast } from "sonner"

import { AppHeader } from "@/components/AppHeader"
import { ChatPanel } from "@/components/ChatPanel"
import { ResolveDialog } from "@/components/ResolveDialog"
import { SeverityBadge } from "@/components/SeverityBadge"
import { StatusBadge } from "@/components/StatusBadge"
import { Timeline } from "@/components/Timeline"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useIncident, useReopenIncident } from "@/hooks/useIncident"
import { ApiError } from "@/lib/api"
import type { IncidentStatus, PostMortem } from "@/lib/types"

const RESOLVABLE: IncidentStatus[] = ["open", "active"]

export function IncidentDetailPage() {
  const { id = "" } = useParams()
  const qc = useQueryClient()
  const { data: incident, isLoading, isError } = useIncident(id)
  const reopen = useReopenIncident(id)

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

  return (
    <div className="flex h-screen flex-col bg-muted/30">
      <AppHeader />

      {/* Intestazione incidente */}
      <div className="container pt-4">
        <Card className="px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <Button asChild variant="ghost" size="icon" className="shrink-0" aria-label="Torna alla dashboard">
                <Link to="/">
                  <ArrowLeft className="h-4 w-4" />
                </Link>
              </Button>
              <div className="min-w-0">
                <h1 className="truncate text-base font-semibold tracking-tight">{incident.title}</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  <StatusBadge status={incident.status} />
                  <SeverityBadge severity={incident.severity} />
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
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
      <div className="container grid min-h-0 flex-1 grid-cols-1 gap-4 py-4 lg:grid-cols-[2fr_3fr]">
        {/* Sinistra: descrizione, timeline, remediation, post-mortem */}
        <div className="min-h-0 space-y-4 overflow-y-auto pr-1">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Descrizione</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm text-foreground/90">{incident.description}</p>
            </CardContent>
          </Card>

          {incident.post_mortem && <PostMortemCard pm={incident.post_mortem} />}

          {incident.remediation.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Remediation</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {incident.remediation.map((step) => (
                    <li key={step.id} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      <div>
                        <span>{step.description}</span>
                        <span className="ml-2 text-sm text-muted-foreground">[{step.source}]</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

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
        <Card className="flex min-h-0 flex-col overflow-hidden">
          <CardContent className="min-h-0 flex-1 p-0">
            <ChatPanel
              key={incident.id}
              incidentId={incident.id}
              status={incident.status}
              initialEvents={incident.timeline}
              initialDraft={incident.status === "open" ? incident.description : ""}
              onTurnComplete={() => qc.invalidateQueries({ queryKey: ["incident", incident.id] })}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function PostMortemCard({ pm }: { pm: PostMortem }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Post-mortem</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {pm.root_cause && <Field label="Causa radice" value={pm.root_cause} />}
        {pm.impact && <Field label="Impatto" value={pm.impact} />}
        {pm.detection && <Field label="Rilevamento" value={pm.detection} />}
        {pm.resolution_steps && pm.resolution_steps.length > 0 && (
          <div>
            <div className="mb-1 text-sm font-medium text-muted-foreground">Passi di risoluzione</div>
            <ul className="list-inside list-disc space-y-1">
              {pm.resolution_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}
        {pm.action_items && pm.action_items.length > 0 && (
          <div>
            <div className="mb-1 text-sm font-medium text-muted-foreground">Action item</div>
            <ul className="list-inside list-disc space-y-1">
              {pm.action_items.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}
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
