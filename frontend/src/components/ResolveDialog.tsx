import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useResolveIncident } from "@/hooks/useIncident";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ButtonProps } from "@/components/ui/button";

export function ResolveDialog({
  incidentId,
  triggerSize,
  triggerClassName,
}: {
  incidentId: string;
  triggerSize?: ButtonProps["size"];
  triggerClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const resolve = useResolveIncident(incidentId);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    try {
      await resolve.mutateAsync({ resolution_summary: summary.trim() });
      toast.success("Incidente risolto");
      setOpen(false);
      setSummary("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Risoluzione fallita");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size={triggerSize} className={triggerClassName}>
          Risolvi
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-card shadow-2xl">
        <DialogHeader className="space-y-3">
          <DialogTitle className="text-xl">Risolvi incidente</DialogTitle>
          <DialogDescription className="leading-5">
            Riepiloga come è stato risolto l'incidente.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="summary">Riepilogo risoluzione</Label>
            <Textarea
              id="summary"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Es. Sostituito il modulo di comunicazione Profinet del PLC, ripresa produzione."
              rows={3}
              className="bg-background"
              autoFocus
              required
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
  );
}
