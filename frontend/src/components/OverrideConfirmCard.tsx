import { SeverityBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { useTeams } from "@/hooks/useTeams";
import type { OverrideProposal } from "@/lib/types";

export function OverrideConfirmCard({
  proposal,
  onConfirm,
  onCancel,
  isPending,
}: {
  proposal: OverrideProposal;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const { teamName } = useTeams();
  const hasChanges =
    proposal.severity !== null || proposal.add_teams.length > 0 || proposal.remove_teams.length > 0;

  return (
    <div className="space-y-2.5 rounded-lg border bg-card p-3 text-sm">
      <p className="font-medium text-foreground/90">
        {proposal.description || "Proposta di modifica classificazione"}
      </p>

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
              <span className="w-28 shrink-0 pt-0.5 text-xs text-muted-foreground">
                Aggiungi team
              </span>
              <div className="flex flex-wrap gap-1">
                {proposal.add_teams.map((t) => (
                  <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium">
                    {teamName(t)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {proposal.remove_teams.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="w-28 shrink-0 pt-0.5 text-xs text-muted-foreground">
                Rimuovi team
              </span>
              <div className="flex flex-wrap gap-1">
                {proposal.remove_teams.map((t) => (
                  <span
                    key={t}
                    className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium line-through opacity-60"
                  >
                    {teamName(t)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <Button size="sm" onClick={onConfirm} disabled={isPending || !hasChanges}>
          Conferma
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} disabled={isPending}>
          Annulla
        </Button>
      </div>
    </div>
  );
}
