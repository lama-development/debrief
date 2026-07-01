import { CheckCircle, XCircle } from "lucide-react"

import { SeverityBadge } from "@/components/SeverityBadge"
import { Button } from "@/components/ui/button"
import type { OverrideProposal } from "@/lib/types"

const TEAM_LABELS: Record<string, string> = {
  IT_INTERNAL: "IT Interno",
  IT_DEV: "Sviluppatori Genius",
  IT_EXTERNAL: "2000net Srl",
  PLC_VENDOR: "Fornitore PLC",
  PRODUCTION: "Reparto Produzione",
  LAB: "Laboratorio",
  MANAGEMENT: "Direzione",
}

export function OverrideConfirmCard({
  proposal,
  onConfirm,
  onCancel,
  isPending,
}: {
  proposal: OverrideProposal
  onConfirm: () => void
  onCancel: () => void
  isPending: boolean
}) {
  const hasChanges =
    proposal.severity !== null ||
    proposal.add_teams.length > 0 ||
    proposal.remove_teams.length > 0

  return (
    <div className="rounded-lg border bg-card p-3 text-sm space-y-2.5">
      <p className="font-medium text-foreground/90">{proposal.description || "Proposta di modifica classificazione"}</p>

      {hasChanges && (
        <div className="space-y-1.5 text-sm">
          {proposal.severity && (
            <div className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-xs text-muted-foreground">Nuova severità</span>
              <SeverityBadge severity={proposal.severity} />
            </div>
          )}
          {proposal.add_teams.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="w-28 shrink-0 text-xs text-muted-foreground pt-0.5">Aggiungi team</span>
              <div className="flex flex-wrap gap-1">
                {proposal.add_teams.map((t) => (
                  <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium">
                    {TEAM_LABELS[t] ?? t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {proposal.remove_teams.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="w-28 shrink-0 text-xs text-muted-foreground pt-0.5">Rimuovi team</span>
              <div className="flex flex-wrap gap-1">
                {proposal.remove_teams.map((t) => (
                  <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium line-through opacity-60">
                    {TEAM_LABELS[t] ?? t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={onConfirm} disabled={isPending || !hasChanges} className="gap-1.5">
          <CheckCircle className="h-3.5 w-3.5" />
          Conferma
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} disabled={isPending} className="gap-1.5">
          <XCircle className="h-3.5 w-3.5" />
          Annulla
        </Button>
      </div>
    </div>
  )
}
