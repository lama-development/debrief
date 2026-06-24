import {
  CheckCircle2,
  ClipboardCheck,
  Flag,
  ShieldAlert,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react"

import { formatDateTime } from "@/lib/labels"
import { cn } from "@/lib/utils"
import { AGENT_IDENTITY, DECLARED_CLS } from "@/lib/agents"
import type { TimelineEvent } from "@/lib/types"

// Un milestone è un FATTO saliente del ciclo di vita (non un messaggio di chat).
interface Milestone {
  key: string
  time: string
  label: string
  detail?: string
  icon: LucideIcon
  cls: string
}

// Traduce gli eventi grezzi di timeline nei soli milestone, scartando la
// conversazione (message + prosa degli agenti). La chat mostra il dialogo;
// qui resta la cronologia "ufficiale" dei fatti con data e ora.
function toMilestones(events: TimelineEvent[]): Milestone[] {
  const out: Milestone[] = []
  events.forEach((ev, idx) => {
    // Il primo evento in assoluto è il messaggio di dichiarazione dell'incidente.
    if (idx === 0) {
      out.push({
        key: `${ev.id}-declared`,
        time: ev.timestamp,
        label: "Incidente dichiarato",
        icon: Flag,
        cls: DECLARED_CLS,
      })
      return
    }
    switch (ev.event_type) {
      case "triage":
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: "Classificato dal triage",
          icon: ClipboardCheck,
          cls: AGENT_IDENTITY.triage.timelineCls,
        })
        break
      case "involvement":
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: "Team coinvolto",
          detail: ev.content ?? undefined,
          icon: Users,
          cls: AGENT_IDENTITY.triage.timelineCls,
        })
        break
      case "escalation":
        out.push({
          key: `${ev.id}`,
          time: ev.timestamp,
          label: "Escalation a intervento umano",
          icon: ShieldAlert,
          cls: DECLARED_CLS,
        })
        break
      case "resolution":
        // Distinzione via attore: l'agente PROPONE, una persona CHIUDE l'incidente.
        if (ev.actor === "resolver") {
          out.push({
            key: `${ev.id}`,
            time: ev.timestamp,
            label: "Soluzione proposta dal resolver",
            icon: Wrench,
            cls: AGENT_IDENTITY.resolver.timelineCls,
          })
        } else {
          out.push({
            key: `${ev.id}`,
            time: ev.timestamp,
            label: "Incidente risolto",
            icon: CheckCircle2,
            cls: AGENT_IDENTITY.resolver.timelineCls,
          })
        }
        break
      // "message" e ogni altro evento conversazionale: ignorati (sono nella chat).
    }
  })
  return out
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const milestones = toMilestones(events)

  if (milestones.length === 0) {
    return <p className="text-sm text-muted-foreground">Nessun evento saliente ancora registrato.</p>
  }

  return (
    <ol className="relative space-y-4 before:absolute before:left-[13px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-border/50">
      {milestones.map((m) => {
        const Icon = m.icon
        return (
          <li key={m.key} className="relative flex items-center gap-3">
            <span className="z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-background">
              <span className={cn("flex h-7 w-7 items-center justify-center rounded-full border border-current/20", m.cls)}>
                <Icon className="h-3.5 w-3.5" />
              </span>
            </span>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium leading-tight">{m.label}</span>
                <span className="text-sm text-muted-foreground/70 shrink-0">{formatDateTime(m.time)}</span>
              </div>
              {m.detail && <p className="text-sm text-muted-foreground mt-0.5">{m.detail}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
