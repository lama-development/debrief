// Tipi allineati 1:1 agli output del backend (src/debrief/schemas.py e service.py).
// Niente enum TS (il tsconfig usa erasableSyntaxOnly): usiamo union di stringhe.

export type Severity = "SEV1" | "SEV2" | "SEV3" | "SEV4"

export type IncidentStatus = "open" | "active" | "resolved"

export type AgentRole = "triage" | "investigator" | "resolver" | "none"

export interface User {
  id: string
  username: string
  created_at?: string
}

export interface Incident {
  id: string
  title: string
  description: string
  severity: Severity | null
  status: IncidentStatus
  created_by: string | null
  session_id: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
}

export interface TimelineEvent {
  id: number
  incident_id: string
  timestamp: string
  // "message" | "triage" | "escalation" | "resolution" | "involvement"
  event_type: string
  actor: string | null
  content: string | null
}

export interface RemediationStep {
  id: number
  incident_id: string
  description: string
  completed: number // SQLite: 0 | 1
  source: string
}

export interface PostMortem {
  incident_id: string
  title: string
  severity: Severity
  impact?: string
  detection?: string
  root_cause?: string
  resolution_steps?: string[]
  action_items?: string[]
  references?: string[]
  timeline?: TimelineEvent[]
}

export interface IncidentDetail extends Incident {
  timeline: TimelineEvent[]
  remediation: RemediationStep[]
  post_mortem: PostMortem | null
}

export interface Metrics {
  by_status: Record<string, number>
  by_severity: Record<string, number>
  mttr_seconds: number | null
  total: number
}

// Output strutturato del triage (evento SSE "triage").
export interface TriageData {
  title: string
  severity: Severity
  affected_systems: string[]
  suggested_teams: string[]
  summary: string
  needs_clarification: boolean
  clarifying_questions: string[]
  confidence: number
}

// Eventi emessi dallo streaming della chat (service.stream_chat).
export type ChatEvent =
  | { type: "routing"; agent: AgentRole; reason: string }
  | { type: "tool"; name: string }
  | { type: "token"; content: string }
  | { type: "triage"; data: TriageData }
  | { type: "done"; status: IncidentStatus; incident_id: string }
  | { type: "error"; message: string }
