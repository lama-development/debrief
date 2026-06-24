import { ClipboardCheck } from "lucide-react"

import { SeverityBadge } from "@/components/SeverityBadge"
import type { TriageData } from "@/lib/types"

// Card che visualizza l'output strutturato del triage (evento SSE "triage").
export function TriageCard({ data }: { data: TriageData }) {
  return (
    <div className="rounded-lg border bg-card p-3 text-sm">
      <div className="mb-2 flex items-center gap-2 font-medium">
        <ClipboardCheck className="h-4 w-4 text-blue-600" />
        Classificazione triage
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={data.severity} />
        <span className="text-sm text-muted-foreground">
          Confidenza {Math.round(data.confidence * 100)}%
        </span>
      </div>

      <dl className="mt-3 space-y-1.5 text-sm">
        {data.affected_systems.length > 0 && (
          <div className="flex gap-2">
            <dt className="w-28 shrink-0 text-muted-foreground">Sistemi coinvolti</dt>
            <dd>{data.affected_systems.join(", ")}</dd>
          </div>
        )}
        {data.suggested_teams.length > 0 && (
          <div className="flex gap-2">
            <dt className="w-28 shrink-0 text-muted-foreground">Team suggeriti</dt>
            <dd>{data.suggested_teams.join(", ")}</dd>
          </div>
        )}
      </dl>
    </div>
  )
}
