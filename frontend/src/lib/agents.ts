export interface AgentIdentity {
  label: string;
  iconCls: string; // text + bg per icone/avatar
  bubbleCls: string; // bubble dell'assistente in chat
  timelineCls: string; // icona nella timeline
}

const BOT_ICON_CLS = "border border-primary/25 bg-primary/10 text-primary";
const BOT_BUBBLE_CLS = "border border-primary/20 bg-primary/5 text-foreground dark:bg-primary/10";
const BOT_TIMELINE_CLS = "border-primary/25 bg-primary/10 text-primary";

function botIdentity(label: string): AgentIdentity {
  return {
    label,
    iconCls: BOT_ICON_CLS,
    bubbleCls: BOT_BUBBLE_CLS,
    timelineCls: BOT_TIMELINE_CLS,
  };
}

export const AGENT_IDENTITY: Record<string, AgentIdentity> = {
  triage: botIdentity("Triage"),
  investigator: botIdentity("Investigator"),
  resolver: botIdentity("Resolver"),
  debrief: botIdentity("Debrief"),
  none: {
    label: "Sistema",
    iconCls: "bg-muted text-muted-foreground",
    bubbleCls: "border border-border bg-secondary/80 text-foreground dark:bg-secondary/60",
    timelineCls: "text-muted-foreground bg-muted border-border",
  },
};

export function getAgentIdentity(agent?: string): AgentIdentity {
  return AGENT_IDENTITY[agent ?? "none"] ?? AGENT_IDENTITY.none;
}
