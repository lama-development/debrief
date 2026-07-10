import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Bot, ExternalLink, Loader2, Search, Send, User as UserIcon } from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { OverrideConfirmCard } from "@/components/OverrideConfirmCard";
import { TriageCard } from "@/components/TriageCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { streamChat } from "@/lib/chat";
import { incidentsApi, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getAgentIdentity } from "@/lib/agents";
import type {
  ChatEvent,
  HumanHelpRequest,
  IncidentStatus,
  OverrideProposal,
  TimelineEvent,
  TriageData,
} from "@/lib/types";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  agent?: string;
  content: string;
  triage?: TriageData;
  overrideProposal?: OverrideProposal;
  humanHelp?: HumanHelpRequest;
  overrideDismissed?: boolean;
}

const ASSISTANT_ACTORS = new Set(["triage", "investigator", "resolver"]);
const CLOSED_STATUSES: IncidentStatus[] = ["resolved"];
const INCIDENT_REFERENCE_RE = /\b(INC-\d{3,})\b/g;
const EXISTING_INCIDENT_LINK_RE = /(\[INC-\d{3,}\]\([^)]+\))/g;
const CODE_FENCE_OR_INLINE_RE = /(```[\s\S]*?```|`[^`\n]+`)/g;

function linkIncidentReferences(markdown: string) {
  return markdown
    .split(CODE_FENCE_OR_INLINE_RE)
    .map((codeOrText, idx) => {
      if (idx % 2 === 1) return codeOrText;
      return codeOrText
        .split(EXISTING_INCIDENT_LINK_RE)
        .map((part, partIdx) => {
          if (partIdx % 2 === 1) return part;
          return part.replace(INCIDENT_REFERENCE_RE, "[$1](/incidents/$1)");
        })
        .join("");
    })
    .join("");
}

// Costruisce la cronologia iniziale della chat dagli eventi di timeline.
function seedMessages(events: TimelineEvent[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  events.forEach((ev, idx) => {
    // idx 0 = dichiarazione dell'incidente (= la descrizione): è già mostrata
    // nella card "Descrizione" e nel milestone "Incidente dichiarato", quindi non
    // la ripetiamo come bolla di chat.
    if (idx === 0) return;
    if (ev.event_type === "involvement") return; // mostrato nella timeline a sinistra
    if (ev.event_type === "disinvolvement") return;
    if (ev.event_type === "override") return;
    const isAssistant = ASSISTANT_ACTORS.has(ev.actor ?? "");
    out.push({
      id: ev.id,
      role: isAssistant ? "assistant" : "user",
      agent: isAssistant ? (ev.actor ?? undefined) : undefined,
      content: ev.content ?? "",
    });
  });
  return out;
}

export function ChatPanel({
  incidentId,
  status,
  initialEvents,
  initialDraft = "",
  onTurnComplete,
  onClassificationChanged,
}: {
  incidentId: string;
  status: IncidentStatus;
  initialEvents: TimelineEvent[];
  initialDraft?: string;
  onTurnComplete: () => void;
  onClassificationChanged?: () => void;
}) {
  // Seed una volta sola al mount (il parent passa key={incidentId} -> remount per incidente).
  const [messages, setMessages] = useState<ChatMessage[]>(() => seedMessages(initialEvents));
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [overridePending, setOverridePending] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const nextLocalId = useRef(-1); // id negativi per i messaggi creati lato client
  const autoSent = useRef(false);
  // Traccia il messaggio assistente attualmente in costruzione: aggiornato da
  // ogni evento "phase" così i token successivi vanno nella bolla giusta.
  const activeAssistantId = useRef(-1);

  const closed = CLOSED_STATUSES.includes(status);

  // Auto-scroll in fondo a ogni aggiornamento.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, activeTool]);

  // Classificazione automatica: appena si apre un incidente "open" non ancora
  // gestito, avviamo da soli il triage sulla descrizione, nessun click richiesto.
  // (Il backend è pensato così: il primo messaggio di chat è la descrizione e il
  // router lo instrada al triage.)
  useEffect(() => {
    if (autoSent.current) return;
    if (status !== "open" || !initialDraft) return;
    if (initialEvents.some((e) => ASSISTANT_ACTORS.has(e.actor ?? ""))) return;
    autoSent.current = true;
    void send(initialDraft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send();
  }

  // textArg valorizzato = invio automatico (es. auto-triage); undefined = dall'input utente.
  async function send(textArg?: string) {
    const text = (textArg ?? input).trim();
    if (!text || streaming) return;

    const userMsg: ChatMessage = { id: nextLocalId.current--, role: "user", content: text };
    const assistantId = nextLocalId.current--;
    activeAssistantId.current = assistantId;
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }]);
    if (textArg === undefined) setInput("");
    setStreaming(true);
    setActiveTool(null);
    setActiveAgent(null);

    // Legge sempre activeAssistantId.current: si aggiorna automaticamente quando
    // arriva un evento "phase" che crea una nuova bolla per l'agente successivo.
    const patchAssistant = (patch: Partial<ChatMessage>) =>
      setMessages((prev) =>
        prev.map((m) =>
          m.id === activeAssistantId.current
            ? { ...m, ...patch, content: patch.content ?? m.content }
            : m,
        ),
      );
    const appendToken = (token: string) =>
      setMessages((prev) =>
        prev.map((m) =>
          m.id === activeAssistantId.current ? { ...m, content: m.content + token } : m,
        ),
      );

    const onEvent = (ev: ChatEvent) => {
      switch (ev.type) {
        case "routing":
          patchAssistant({ agent: ev.agent });
          setActiveAgent(ev.agent);
          break;
        case "tool":
          setActiveTool(ev.name);
          break;
        case "triage":
          patchAssistant({ agent: "triage", triage: ev.data });
          break;
        case "override_proposed":
          patchAssistant({ agent: "override", overrideProposal: ev.data });
          break;
        case "human_help_required":
          patchAssistant({ agent: "resolver", humanHelp: ev.data });
          break;
        case "phase": {
          const newId = nextLocalId.current--;
          activeAssistantId.current = newId;
          setActiveTool(null);
          setActiveAgent(ev.agent);
          setMessages((prev) => [
            ...prev,
            { id: newId, role: "assistant", content: "", agent: ev.agent },
          ]);
          break;
        }
        case "token":
          appendToken(ev.content);
          break;
        case "done":
          setActiveTool(null);
          setActiveAgent(null);
          onTurnComplete();
          break;
        case "error":
          toast.error(ev.message);
          appendToken(`\n\n[errore: ${ev.message}]`);
          break;
      }
    };

    try {
      await streamChat(incidentId, text, onEvent);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Errore durante la chat");
      patchAssistant({ content: "Si è verificato un errore. Riprova." });
    } finally {
      setStreaming(false);
      setActiveTool(null);
      setActiveAgent(null);
    }
  }

  async function handleOverrideConfirm(msgId: number) {
    const msg = messages.find((m) => m.id === msgId);
    if (!msg?.overrideProposal) return;
    const { severity, add_teams, remove_teams } = msg.overrideProposal;
    setOverridePending(true);
    try {
      await incidentsApi.patchClassification(incidentId, {
        severity: severity ?? undefined,
        add_teams,
        remove_teams,
      });
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, overrideDismissed: true } : m)),
      );
      toast.success("Classificazione aggiornata");
      onClassificationChanged?.();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Aggiornamento fallito");
    } finally {
      setOverridePending(false);
    }
  }

  return (
    <div className="relative flex h-full flex-col">
      {/* Cronologia */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4 pb-24">
        {messages.length === 0 && (
          <p className="mt-8 text-center text-sm text-muted-foreground">
            Invia un messaggio per avviare il triage dell'incidente.
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            incidentId={incidentId}
            onOverrideConfirm={handleOverrideConfirm}
            overridePending={overridePending}
          />
        ))}
        {activeTool && <ToolBubble agent={activeAgent} />}
      </div>

      {/* Input floating */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background/80 via-60% to-transparent px-3 pb-3 pt-8">
        <form onSubmit={onSubmit}>
          {closed ? (
            <p className="py-1 text-center text-sm text-muted-foreground">
              Incidente chiuso. Riaprilo per continuare la conversazione.
            </p>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border bg-background/80 px-3 py-2 shadow-lg">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                placeholder="Scrivi un messaggio…"
                rows={1}
                className="min-h-[32px] resize-none border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                disabled={streaming}
              />
              <Button
                type="submit"
                size="icon"
                className="h-8 w-8 shrink-0"
                disabled={streaming || !input.trim()}
              >
                {streaming ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

function ToolBubble({ agent }: { agent: string | null }) {
  const identity = getAgentIdentity(agent ?? undefined);
  return (
    <div className="flex gap-2">
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          identity.iconCls,
        )}
      >
        <Bot className="h-4 w-4" />
      </span>
      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm shadow-sm",
          identity.bubbleCls,
        )}
      >
        <Search className="h-3.5 w-3.5 animate-pulse" />
        <span className="text-muted-foreground">Ricerca in corso…</span>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  incidentId,
  onOverrideConfirm,
  overridePending,
}: {
  message: ChatMessage;
  incidentId: string;
  onOverrideConfirm: (msgId: number) => void;
  overridePending: boolean;
}) {
  const [dismissed, setDismissed] = useState(message.overrideDismissed ?? false);
  const isUser = message.role === "user";
  const identity = getAgentIdentity(message.agent);
  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-primary/15 text-foreground ring-1 ring-inset ring-primary/20"
            : identity.iconCls,
        )}
      >
        {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={cn("max-w-[80%] space-y-2", isUser ? "items-end" : "items-start")}>
        {!isUser && message.agent && message.agent !== "override" && (
          <div className="text-sm font-medium text-muted-foreground">{identity.label}</div>
        )}
        {message.triage && <TriageCard data={message.triage} />}
        {message.overrideProposal && !dismissed && (
          <OverrideConfirmCard
            proposal={message.overrideProposal}
            isPending={overridePending}
            onConfirm={() => onOverrideConfirm(message.id)}
            onCancel={() => setDismissed(true)}
          />
        )}
        {message.humanHelp && <HumanHelpCard incidentId={incidentId} request={message.humanHelp} />}
        {message.content && (
          <div
            className={cn(
              "inline-block rounded-lg px-3 py-2 text-sm shadow-sm",
              isUser
                ? "whitespace-pre-wrap border border-primary/30 bg-primary/15 text-foreground"
                : identity.bubbleCls,
            )}
          >
            {isUser ? (
              message.content
            ) : (
              <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:my-2 prose-p:my-1 prose-code:text-sm prose-pre:my-1 prose-ol:my-1 prose-ul:my-1 prose-li:my-0">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => {
                      const isIncidentLink =
                        href !== undefined && /^\/incidents\/INC-\d{3,}$/.test(href);
                      if (isIncidentLink) {
                        return (
                          <Link
                            to={href}
                            className="inline-flex items-center gap-1 rounded-sm font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                          >
                            {children}
                            <ExternalLink className="h-3 w-3" aria-hidden="true" />
                          </Link>
                        );
                      }

                      return (
                        <a href={href} target="_blank" rel="noreferrer">
                          {children}
                        </a>
                      );
                    },
                  }}
                >
                  {linkIncidentReferences(message.content)}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function HumanHelpCard({ incidentId, request }: { incidentId: string; request: HumanHelpRequest }) {
  const [solution, setSolution] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function submit() {
    if (solution.trim().length < 3) return;
    setSaving(true);
    try {
      await incidentsApi.addHumanSolution(incidentId, solution.trim());
      setSaved(true);
      toast.success("Soluzione acquisita nell'incidente");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Salvataggio fallito");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
      <div>
        <p className="font-medium">È necessario il contributo di una persona</p>
        <p className="text-muted-foreground">{request.reason}</p>
      </div>
      {saved ? (
        <p className="font-medium text-emerald-700 dark:text-emerald-400">
          Soluzione salvata e disponibile per problemi futuri simili.
        </p>
      ) : (
        <>
          <Textarea
            value={solution}
            onChange={(event) => setSolution(event.target.value)}
            placeholder="Descrivi la soluzione trovata dall'esperto..."
            rows={3}
          />
          <Button
            size="sm"
            disabled={saving || solution.trim().length < 3}
            onClick={() => void submit()}
          >
            {saving ? "Salvataggio…" : "Capitalizza questa soluzione"}
          </Button>
        </>
      )}
    </div>
  );
}
