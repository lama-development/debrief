import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { useResolveIncident } from "@/hooks/useIncident"
import { ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

// Dialog di chiusura incidente: riepilogo risoluzione (obbligatorio) + eventuale
// soluzione verificata (alimenta il learning loop come fonte ad alta priorità).
export function ResolveDialog({ incidentId }: { incidentId: string }) {
  const [open, setOpen] = useState(false)
  const [summary, setSummary] = useState("")
  const [verified, setVerified] = useState("")
  const resolve = useResolveIncident(incidentId)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!summary.trim()) return
    try {
      await resolve.mutateAsync({
        resolution_summary: summary.trim(),
        verified_solution: verified.trim() || undefined,
      })
      toast.success("Incidente risolto")
      setOpen(false)
      setSummary("")
      setVerified("")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Risoluzione fallita")
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Risolvi</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Risolvi incidente</DialogTitle>
          <DialogDescription>
            Riepiloga come è stato risolto. La soluzione verificata (opzionale) verrà
            indicizzata come fonte ad alta priorità per incidenti futuri simili.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="summary">Riepilogo risoluzione *</Label>
            <Textarea
              id="summary"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Es. Sostituito il modulo di comunicazione Profinet del PLC, ripresa produzione."
              rows={3}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="verified">Soluzione verificata (opzionale)</Label>
            <Textarea
              id="verified"
              value={verified}
              onChange={(e) => setVerified(e.target.value)}
              placeholder="Procedura riutilizzabile da archiviare come soluzione verificata…"
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={resolve.isPending || !summary.trim()}>
              {resolve.isPending ? "Salvataggio…" : "Conferma risoluzione"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
