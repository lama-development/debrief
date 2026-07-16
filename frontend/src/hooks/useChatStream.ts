import { useCallback, useReducer, useRef } from "react";
import { toast } from "sonner";

import { ApiError, incidentsApi } from "@/lib/api";
import { streamChat } from "@/lib/chat";
import type {
  ChatEvent,
  HumanHelpRequest,
  IncidentStatus,
  OverrideProposal,
  TimelineEvent,
  TriageData,
  User,
} from "@/lib/types";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  agent?: string;
  content: string;
  timestamp: string;
  senderId?: string;
  senderUsername?: string;
  senderTeam?: string;
  triage?: TriageData;
  overrideProposal?: OverrideProposal;
  humanHelp?: HumanHelpRequest;
  overrideStatus?: "idle" | "pending" | "confirmed" | "cancelled";
  isFinalResolution?: boolean;
}

interface ChatState {
  messages: ChatMessage[];
  streaming: boolean;
  toolActive: boolean;
  activeAgent: string | null;
}

type ChatAction =
  | { type: "add_messages"; messages: ChatMessage[] }
  | { type: "patch_message"; id: number; patch: Partial<ChatMessage> }
  | { type: "append_token"; id: number; token: string }
  | { type: "remove_if_empty"; id: number }
  | { type: "stream_started" }
  | { type: "tool_started" }
  | { type: "agent_changed"; agent: string | null }
  | { type: "stream_finished" };

const ASSISTANT_ACTORS = new Set(["triage", "investigator", "resolver", "debrief"]);
const DEBRIEF_MENTION_RE = /(^|[^\w@])@debrief\b/i;

export function hasAssistantEvents(events: TimelineEvent[]) {
  return events.some((event) => ASSISTANT_ACTORS.has(event.actor ?? ""));
}

function seedMessages(events: TimelineEvent[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  events.forEach((event, index) => {
    if (index === 0) return;
    if (["involvement", "disinvolvement", "override", "reopen"].includes(event.event_type)) {
      return;
    }

    const isAssistant = ASSISTANT_ACTORS.has(event.actor ?? "");
    messages.push({
      id: event.id,
      role: isAssistant ? "assistant" : "user",
      agent: isAssistant ? (event.actor ?? undefined) : undefined,
      timestamp: event.timestamp,
      senderId: isAssistant ? undefined : (event.actor_user_id ?? event.actor ?? undefined),
      senderUsername: isAssistant ? undefined : (event.actor_username ?? event.actor ?? "Utente"),
      senderTeam: isAssistant ? undefined : (event.actor_team_name ?? undefined),
      content: event.content ?? "",
      isFinalResolution: event.event_type === "resolution" && event.actor !== "resolver",
    });
  });
  return messages;
}

function reducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "add_messages":
      return { ...state, messages: [...state.messages, ...action.messages] };
    case "patch_message":
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? {
                ...message,
                ...action.patch,
                content: action.patch.content ?? message.content,
              }
            : message,
        ),
      };
    case "append_token":
      return {
        ...state,
        messages: state.messages.map((message) =>
          message.id === action.id
            ? { ...message, content: message.content + action.token }
            : message,
        ),
      };
    case "remove_if_empty":
      return {
        ...state,
        messages: state.messages.filter(
          (message) =>
            message.id !== action.id ||
            Boolean(
              message.content || message.triage || message.overrideProposal || message.humanHelp,
            ),
        ),
      };
    case "stream_started":
      return { ...state, streaming: true, toolActive: false, activeAgent: null };
    case "tool_started":
      return { ...state, toolActive: true };
    case "agent_changed":
      return { ...state, toolActive: false, activeAgent: action.agent };
    case "stream_finished":
      return { ...state, streaming: false, toolActive: false, activeAgent: null };
  }
}

export function useChatStream({
  incidentId,
  status,
  initialEvents,
  user,
  onIncidentChanged,
}: {
  incidentId: string;
  status: IncidentStatus;
  initialEvents: TimelineEvent[];
  user: User | null;
  onIncidentChanged: () => void;
}) {
  const [state, dispatch] = useReducer(reducer, initialEvents, (events): ChatState => ({
    messages: seedMessages(events),
    streaming: false,
    toolActive: false,
    activeAgent: null,
  }));
  const nextLocalId = useRef(-1);
  const activeAssistantId = useRef<number | null>(null);
  const streamInFlight = useRef(false);
  const overrideRequestsInFlight = useRef(new Set<number>());

  const send = useCallback(
    async (text: string) => {
      const normalized = text.trim();
      if (!normalized || streamInFlight.current) return false;
      streamInFlight.current = true;

      const userMessage: ChatMessage = {
        id: nextLocalId.current--,
        role: "user",
        content: normalized,
        timestamp: new Date().toISOString(),
        senderId: user?.id,
        senderUsername: user?.username,
        senderTeam: user?.team_name,
      };
      const expectsAssistant = status === "open" || DEBRIEF_MENTION_RE.test(normalized);
      const assistantId = expectsAssistant ? nextLocalId.current-- : null;
      activeAssistantId.current = assistantId;

      dispatch({
        type: "add_messages",
        messages: [
          userMessage,
          ...(assistantId === null
            ? []
            : [
                {
                  id: assistantId,
                  role: "assistant" as const,
                  content: "",
                  timestamp: new Date().toISOString(),
                },
              ]),
        ],
      });
      dispatch({ type: "stream_started" });

      const patchAssistant = (patch: Partial<ChatMessage>) => {
        const id = activeAssistantId.current;
        if (id !== null) dispatch({ type: "patch_message", id, patch });
      };
      const appendToken = (token: string) => {
        const id = activeAssistantId.current;
        if (id !== null) dispatch({ type: "append_token", id, token });
      };
      const ensureAssistant = () => {
        if (activeAssistantId.current !== null) return;
        const id = nextLocalId.current--;
        activeAssistantId.current = id;
        dispatch({
          type: "add_messages",
          messages: [
            {
              id,
              role: "assistant",
              content: "",
              timestamp: new Date().toISOString(),
            },
          ],
        });
      };

      let streamFailed = false;
      const onEvent = (event: ChatEvent) => {
        switch (event.type) {
          case "routing": {
            ensureAssistant();
            const agent = event.agent === "none" ? "debrief" : event.agent;
            patchAssistant({ agent });
            dispatch({ type: "agent_changed", agent });
            break;
          }
          case "tool":
            dispatch({ type: "tool_started" });
            break;
          case "triage":
            patchAssistant({ agent: "triage", triage: event.data });
            break;
          case "override_proposed":
            patchAssistant({ agent: "override", overrideProposal: event.data });
            break;
          case "human_help_required":
            patchAssistant({ agent: "resolver", humanHelp: event.data });
            break;
          case "phase": {
            const id = nextLocalId.current--;
            activeAssistantId.current = id;
            dispatch({ type: "agent_changed", agent: event.agent });
            dispatch({
              type: "add_messages",
              messages: [
                {
                  id,
                  role: "assistant",
                  content: "",
                  agent: event.agent,
                  timestamp: new Date().toISOString(),
                },
              ],
            });
            break;
          }
          case "token":
            appendToken(event.content);
            break;
          case "done":
            dispatch({ type: "agent_changed", agent: null });
            onIncidentChanged();
            break;
          case "error":
            streamFailed = true;
            toast.error(event.message);
            appendToken(`\n\n[errore: ${event.message}]`);
            break;
        }
      };

      try {
        await streamChat(incidentId, normalized, onEvent);
        return !streamFailed;
      } catch (error) {
        toast.error(error instanceof ApiError ? error.message : "Errore durante la chat");
        patchAssistant({ content: "Si è verificato un errore. Riprova." });
        return false;
      } finally {
        const emptyAssistantId = activeAssistantId.current;
        if (emptyAssistantId !== null) {
          dispatch({ type: "remove_if_empty", id: emptyAssistantId });
        }
        activeAssistantId.current = null;
        streamInFlight.current = false;
        dispatch({ type: "stream_finished" });
      }
    },
    [incidentId, onIncidentChanged, status, user],
  );

  const confirmOverride = useCallback(
    async (messageId: number) => {
      if (overrideRequestsInFlight.current.has(messageId)) return;
      const message = state.messages.find((candidate) => candidate.id === messageId);
      if (!message?.overrideProposal) return;

      const { severity, add_teams, remove_teams } = message.overrideProposal;
      overrideRequestsInFlight.current.add(messageId);
      dispatch({ type: "patch_message", id: messageId, patch: { overrideStatus: "pending" } });
      try {
        await incidentsApi.patchClassification(incidentId, {
          severity: severity ?? undefined,
          add_teams,
          remove_teams,
        });
        dispatch({
          type: "patch_message",
          id: messageId,
          patch: { overrideStatus: "confirmed" },
        });
        toast.success("Classificazione aggiornata");
        onIncidentChanged();
      } catch (error) {
        dispatch({ type: "patch_message", id: messageId, patch: { overrideStatus: "idle" } });
        toast.error(error instanceof ApiError ? error.message : "Aggiornamento fallito");
      } finally {
        overrideRequestsInFlight.current.delete(messageId);
      }
    },
    [incidentId, onIncidentChanged, state.messages],
  );

  const cancelOverride = useCallback((messageId: number) => {
    if (overrideRequestsInFlight.current.has(messageId)) return;
    dispatch({
      type: "patch_message",
      id: messageId,
      patch: { overrideStatus: "cancelled" },
    });
  }, []);

  return {
    ...state,
    send,
    confirmOverride,
    cancelOverride,
  };
}
