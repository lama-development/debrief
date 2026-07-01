import { ClipboardCheck } from "lucide-react"

import { SeverityBadge } from "@/components/SeverityBadge"
import type { TriageData } from "@/lib/types"

export function TriageCard({ data }: { data: TriageData }) {
  const confidence = Math.round(data.confidence * 100)

  return (
    <div className="rounded-lg border bg-card p-3 text-sm">
      <div className="mb-2.5 flex items-center gap-2 font-medium">
        <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
        Classificazione triage
      </div>

      <div className="flex items-center gap-2.5">
        <SeverityBadge severity={data.severity} />
        <span className="text-muted-foreground">{confidence}% confidenza</span>
      </div>

      {data.suggested_teams.length > 0 && (
        <div className="mt-2.5 border-t pt-2.5">
          <div className="flex items-start gap-2">
            <span className="w-20 shrink-0 text-xs font-medium text-muted-foreground pt-0.5">Team</span>
            <div className="flex flex-wrap gap-1">
              {data.suggested_teams.map((t) => (
                <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium">{t}</span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
