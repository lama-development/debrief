import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useCreateIncident } from "@/hooks/useIncidents";
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

// Apre subito la chat, dove avviene il triage iniziale.
export function NewIncidentDialog() {
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const navigate = useNavigate();
  const createIncident = useCreateIncident();

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    try {
      const incident = await createIncident.mutateAsync(description.trim());
      setOpen(false);
      setDescription("");
      navigate(`/incidents/${incident.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Creazione incidente fallita");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Dichiara incidente</Button>
      </DialogTrigger>
      <DialogContent className="bg-card shadow-2xl">
        <DialogHeader className="space-y-3">
          <DialogTitle className="text-xl">Dichiara un incidente</DialogTitle>
          <DialogDescription className="leading-5">
            Descrivi il problema in linguaggio naturale. Il triage lo classificherà automaticamente
            al primo messaggio in chat.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="description">Descrizione</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Es. Il PLC della linea 2 si è fermato con errore Comm Fault, la produzione è bloccata…"
              rows={5}
              className="bg-background"
              autoFocus
              required
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createIncident.isPending || !description.trim()}>
              {createIncident.isPending ? "Creazione…" : "Conferma"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
