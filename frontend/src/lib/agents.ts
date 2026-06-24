export interface AgentIdentity {
  label: string
  iconCls: string   // text + bg per icone/avatar
  bubbleCls: string // bubble dell'assistente in chat
  timelineCls: string // icona nella timeline
}

export const AGENT_IDENTITY: Record<string, AgentIdentity> = {
  triage: {
    label: "Triage",
    iconCls: "bg-blue-100 text-blue-600 border border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/20",
    bubbleCls: "border border-blue-200 bg-blue-50 text-foreground dark:border-blue-500/20 dark:bg-blue-500/10",
    timelineCls: "text-blue-600 bg-blue-100 border-blue-200 dark:bg-blue-500/10 dark:border-blue-500/20",
  },
  investigator: {
    label: "Investigator",
    iconCls: "bg-violet-100 text-violet-600 border border-violet-200 dark:bg-violet-500/15 dark:text-violet-400 dark:border-violet-500/20",
    bubbleCls: "border border-violet-200 bg-violet-50 text-foreground dark:border-violet-500/20 dark:bg-violet-500/10",
    timelineCls: "text-violet-600 bg-violet-100 border-violet-200 dark:bg-violet-500/10 dark:border-violet-500/20",
  },
  resolver: {
    label: "Resolver",
    iconCls: "bg-emerald-100 text-emerald-600 border border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/20",
    bubbleCls: "border border-emerald-200 bg-emerald-50 text-foreground dark:border-emerald-500/20 dark:bg-emerald-500/10",
    timelineCls: "text-emerald-600 bg-emerald-100 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/20",
  },
  none: {
    label: "Sistema",
    iconCls: "bg-muted text-muted-foreground",
    bubbleCls: "border border-border bg-secondary/80 text-foreground dark:bg-secondary/60",
    timelineCls: "text-muted-foreground bg-muted border-border",
  },
}

export const DECLARED_CLS = "text-orange-600 bg-orange-100 border-orange-200 dark:bg-orange-500/10 dark:border-orange-500/20"

export function getAgentIdentity(agent?: string): AgentIdentity {
  return AGENT_IDENTITY[agent ?? "none"] ?? AGENT_IDENTITY.none
}
