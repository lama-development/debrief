import {
  CheckCircle2,
  ClipboardCheck,
  Flag,
  Pencil,
  ShieldAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { formatDateTime } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { AGENT_IDENTITY, DECLARED_CLS } from "@/lib/agents";
import type { TimelineEvent } from "@/lib/types";

// Un milestone è un FATTO saliente del ciclo di vita (non un messaggio di chat).
interface Milestone {
  key: string;
  time: string;
  label: string;
  detail?: string;
  icon: LucideIcon;
  cls: string;
}

// Traduce gli eventi grezzi di timeline nei soli milestone, scartando la
// conversazione (message + prosa degli agenti). La chat mostra il dialogo;
// qui resta la cronologia "ufficiale" dei fatti con data e ora.
function toMilestones(events: TimelineEvent[]): Milestone[] {
  const out: Milestone[] = [];

  // Team assegnati dal triage: aggregati in un'unica riga invece di N milestone separati.
  const triageTeams = events
    .filter((ev) => ev.event_type === "involvement" && ev.actor === "triage")
    .map((ev) => ev.content ?? "")
    .filter(Boolean)
    .join(", ");

  events.forEach((ev, idx) => {
    // Il primo evento in assoluto è il messaggio di dichiarazione dell'incidente.
    if (idx === 0) {
      out.push({
        key: `${ev.id}-declared`,
        time: ev.timestamp,
        label: "Incidente dichiarato",
        icon: Flag,
        cls: DECLARED_CLS,
      });
      return;
    }
    switch (ev.event_type) {
      case "triage":
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: "Classificato dal triage",
          detail: triageTeams || undefined,
          icon: ClipboardCheck,
          cls: AGENT_IDENTITY.triage.timelineCls,
        });
        break;
      // involvement e disinvolvement individuali: il triage li aggrega sopra,
      // quelli umani sono già riassunti nell'evento "override".
      case "involvement":
      case "disinvolvement":
        break;
      case "override": {
        let detail: string | undefined;
        try {
          const parsed = JSON.parse(ev.content ?? "");
          const parts: string[] = [];
          if (parsed.after?.severity && parsed.after.severity !== parsed.before?.severity)
            parts.push(`Severità: ${parsed.before?.severity ?? "—"} → ${parsed.after.severity}`);
          if (parsed.after?.add_teams?.length) parts.push(`+${parsed.after.add_teams.join(", ")}`);
          if (parsed.after?.remove_teams?.length)
            parts.push(`-${parsed.after.remove_teams.join(", ")}`);
          if (parsed.reason) parts.push(`motivo: ${parsed.reason}`);
          detail = parts.join(" · ") || undefined;
        } catch {
          detail = undefined;
        }
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: `Classificazione modificata da ${ev.actor ?? "utente"}`,
          detail,
          icon: Pencil,
          cls: DECLARED_CLS,
        });
        break;
      }
      case "escalation":
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: "Escalation a intervento umano",
          icon: ShieldAlert,
          cls: DECLARED_CLS,
        });
        break;
      case "resolution":
        // Distinzione via attore: l'agente PROPONE, una persona CHIUDE l'incidente.
        if (ev.actor === "resolver") {
          out.push({
            key: `${ev.id}`,
            time: ev.timestamp,
            label: "Soluzione proposta dal resolver",
            icon: Wrench,
            cls: AGENT_IDENTITY.resolver.timelineCls,
          });
        } else {
          out.push({
            key: `${ev.id}`,
            time: ev.timestamp,
            label: "Incidente risolto",
            icon: CheckCircle2,
            cls: AGENT_IDENTITY.resolver.timelineCls,
          });
        }
        break;
      // "message" e ogni altro evento conversazionale: ignorati (sono nella chat).
    }
  });
  return out;
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const milestones = toMilestones(events);

  if (milestones.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Nessun evento saliente ancora registrato.</p>
    );
  }

  return (
    <ol className="relative space-y-4 before:absolute before:left-[13px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-border/50">
      {milestones.map((m) => {
        const Icon = m.icon;
        return (
          <li key={m.key} className="relative flex items-center gap-3">
            <span className="z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-background">
              <span
                className={cn(
                  "border-current/20 flex h-7 w-7 items-center justify-center rounded-full border",
                  m.cls,
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </span>
            </span>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium leading-tight">{m.label}</span>
                <span className="shrink-0 text-sm text-muted-foreground/70">
                  {formatDateTime(m.time)}
                </span>
              </div>
              {m.detail && <p className="mt-0.5 text-sm text-muted-foreground">{m.detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
