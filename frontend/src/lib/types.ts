// Contratti allineati alle risposte del server; tipi unione al posto degli enum TS.

export type Severity = "SEV1" | "SEV2" | "SEV3" | "SEV4";

export type IncidentStatus = "open" | "active" | "resolved";

type AgentRole = "triage" | "investigator" | "resolver" | "none";

export interface User {
  id: string;
  username: string;
  team_id: string;
  team_name: string;
  created_at?: string;
}

export interface Team {
  id: string;
  name: string;
  description: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity | null;
  status: IncidentStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface TimelineEvent {
  id: number;
  incident_id: string;
  timestamp: string;
  // "message" | "triage" | "escalation" | "resolution" | "reopen" | "involvement"
  event_type: string;
  actor: string | null;
  actor_user_id: string | null;
  actor_username: string | null;
  actor_team_id: string | null;
  actor_team_name: string | null;
  content: string | null;
}

export interface DebriefReport {
  incident_id: string;
  title: string;
  severity: Severity;
  resolution?: string;
  timeline?: TimelineEvent[];
}

interface IncidentParticipant {
  id: string;
  username: string;
  team_id: string;
  team_name: string;
  joined_at: string;
  last_activity_at: string;
}

export interface IncidentDetail extends Incident {
  involved_teams: string[];
  timeline: TimelineEvent[];
  debrief_report: DebriefReport | null;
  participants: IncidentParticipant[];
}

export interface ClassificationOverrideRequest {
  severity?: Severity;
  add_teams?: string[];
  remove_teams?: string[];
}

export interface Metrics {
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  mttr_seconds: number | null;
  total: number;
}

// Risposta strutturata del triage, ricevuta nell'evento SSE omonimo.
export interface TriageData {
  title: string;
  severity: Severity;
  suggested_teams: string[];
  summary: string;
  needs_clarification: boolean;
  clarifying_questions: string[];
  confidence: number;
}

export interface OverrideProposal {
  severity: Severity | null;
  add_teams: string[];
  remove_teams: string[];
  description: string;
}

export interface HumanHelpRequest {
  problem_context: string;
  reason: string;
}

// Eventi emessi dal flusso della chat (`service.stream_chat`).
export type ChatEvent =
  | { type: "routing"; agent: AgentRole; reason: string }
  | { type: "tool"; name: string }
  | { type: "token"; content: string }
  | { type: "triage"; data: TriageData }
  | { type: "override_proposed"; data: OverrideProposal }
  | { type: "human_help_required"; data: HumanHelpRequest }
  | { type: "done"; status: IncidentStatus; incident_id: string }
  | { type: "error"; message: string };
