import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Bot, ExternalLink, Hash, Loader2, Search, Send, User as UserIcon } from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { OverrideConfirmCard } from "@/components/OverrideConfirmCard";
import { useAuth } from "@/auth/AuthContext";
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
  senderId?: string;
  senderUsername?: string;
  senderTeam?: string;
  triage?: TriageData;
  overrideProposal?: OverrideProposal;
  humanHelp?: HumanHelpRequest;
  overrideDismissed?: boolean;
}

const ASSISTANT_ACTORS = new Set(["triage", "investigator", "resolver", "debrief"]);
const CLOSED_STATUSES: IncidentStatus[] = ["resolved"];
// Gli LLM possono scrivere l'ID con trattini tipografici Unicode (es. INC‑003)
// invece del normale "-" ASCII. Accettiamo entrambe le forme e costruiamo poi
// sempre un URL canonico /incidents/INC-003.
const INCIDENT_REFERENCE_RE = /\bINC[-\u2010\u2011\u2012\u2013\u2014\u2015\u2212](\d{3,})\b/g;
const EXISTING_INCIDENT_LINK_RE = /(\[INC-\d{3,}\]\([^)]+\))/g;
const CODE_FENCE_OR_INLINE_RE = /(```[\s\S]*?```|`[^`\n]+`)/g;
const DEBRIEF_MENTION_RE = /(^|\s)@debrief\b/i;

function mentionAtCursor(value: string, cursor: number) {
  const match = value.slice(0, cursor).match(/(^|\s)@([a-zA-Z0-9_-]*)$/);
  if (!match || !"debrief".startsWith(match[2].toLowerCase())) return null;
  return {
    start: cursor - match[0].length + match[1].length,
    end: cursor,
  };
}

function renderHumanMessage(content: string) {
  return content.split(/(@debrief\b)/gi).map((part, index) =>
    /^@debrief$/i.test(part) ? (
      <span
        key={`${part}-${index}`}
        className="rounded bg-primary/10 px-0.5 font-semibold text-primary"
      >
        {part}
      </span>
    ) : (
      part
    ),
  );
}

function linkIncidentReferences(markdown: string) {
  return markdown
    .split(CODE_FENCE_OR_INLINE_RE)
    .map((codeOrText, idx) => {
      if (idx % 2 === 1) return codeOrText;
      return codeOrText
        .replace(/<br\s*\/?>|<\/br>/gi, "  \n")
        .split(EXISTING_INCIDENT_LINK_RE)
        .map((part, partIdx) => {
          if (partIdx % 2 === 1) return part;
          return part.replace(
            INCIDENT_REFERENCE_RE,
            (_match, digits: string) => `[INC-${digits}](/incidents/INC-${digits})`,
          );
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
    if (ev.event_type === "reopen") return;
    const isAssistant = ASSISTANT_ACTORS.has(ev.actor ?? "");
    out.push({
      id: ev.id,
      role: isAssistant ? "assistant" : "user",
      agent: isAssistant ? (ev.actor ?? undefined) : undefined,
      senderId: isAssistant ? undefined : (ev.actor ?? undefined),
      senderUsername: isAssistant ? undefined : (ev.actor_username ?? ev.actor ?? "Utente"),
      senderTeam: isAssistant ? undefined : (ev.actor_team_name ?? undefined),
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
  const { user } = useAuth();
  // Seed una volta sola al mount (il parent passa key={incidentId} -> remount per incidente).
  const [messages, setMessages] = useState<ChatMessage[]>(() => seedMessages(initialEvents));
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [overridePending, setOverridePending] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const nextLocalId = useRef(-1); // id negativi per i messaggi creati lato client
  const autoSent = useRef(false);
  // Traccia il messaggio assistente attualmente in costruzione: aggiornato da
  // ogni evento "phase" così i token successivi vanno nella bolla giusta.
  const activeAssistantId = useRef<number | null>(null);

  const closed = CLOSED_STATUSES.includes(status);
  const activeMention = mentionAtCursor(input, cursorPosition);

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

  function completeMention() {
    const match = mentionAtCursor(input, textareaRef.current?.selectionStart ?? cursorPosition);
    if (!match) return;
    const nextInput = `${input.slice(0, match.start)}@debrief ${input.slice(match.end)}`;
    const nextCursor = match.start + "@debrief ".length;
    setInput(nextInput);
    setCursorPosition(nextCursor);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(nextCursor, nextCursor);
    });
  }

  // textArg valorizzato = invio automatico (es. auto-triage); undefined = dall'input utente.
  async function send(textArg?: string) {
    const text = (textArg ?? input).trim();
    if (!text || streaming) return;

    const userMsg: ChatMessage = {
      id: nextLocalId.current--,
      role: "user",
      content: text,
      senderId: user?.id,
      senderUsername: user?.username,
      senderTeam: user?.team_name,
    };
    const expectsAssistant = status === "open" || DEBRIEF_MENTION_RE.test(text);
    const assistantId = expectsAssistant ? nextLocalId.current-- : null;
    activeAssistantId.current = assistantId;
    setMessages((prev) => [
      ...prev,
      userMsg,
      ...(assistantId === null
        ? []
        : [{ id: assistantId, role: "assistant" as const, content: "" }]),
    ]);
    if (textArg === undefined) setInput("");
    setStreaming(true);
    setActiveTool(null);
    setActiveAgent(null);

    // Legge sempre activeAssistantId.current: si aggiorna automaticamente quando
    // arriva un evento "phase" che crea una nuova bolla per l'agente successivo.
    const patchAssistant = (patch: Partial<ChatMessage>) =>
      setMessages((prev) =>
        prev.map((m) =>
          activeAssistantId.current !== null && m.id === activeAssistantId.current
            ? { ...m, ...patch, content: patch.content ?? m.content }
            : m,
        ),
      );
    const appendToken = (token: string) =>
      setMessages((prev) =>
        prev.map((m) =>
          activeAssistantId.current !== null && m.id === activeAssistantId.current
            ? { ...m, content: m.content + token }
            : m,
        ),
      );

    const onEvent = (ev: ChatEvent) => {
      switch (ev.type) {
        case "routing":
          patchAssistant({ agent: ev.agent === "none" ? "debrief" : ev.agent });
          setActiveAgent(ev.agent === "none" ? "debrief" : ev.agent);
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
      const emptyAssistantId = activeAssistantId.current;
      if (emptyAssistantId !== null) {
        setMessages((prev) =>
          prev.filter(
            (message) =>
              message.id !== emptyAssistantId ||
              Boolean(
                message.content || message.triage || message.overrideProposal || message.humanHelp,
              ),
          ),
        );
      }
      activeAssistantId.current = null;
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
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2 sm:px-4 sm:py-2.5">
        <span className="text-sm font-medium">Chat incidente</span>
        <span className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground">
          <Hash className="h-3.5 w-3.5" aria-hidden="true" />
          {incidentId}
        </span>
      </div>

      {/* Cronologia */}
      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto px-3 py-3 pb-20 sm:space-y-4 sm:p-4 sm:pb-24"
      >
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
            currentUserId={user?.id}
          />
        ))}
        {activeTool && <ToolBubble agent={activeAgent} />}
      </div>

      {/* Input floating */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background/80 via-60% to-transparent px-2 pb-2 pt-6 sm:px-3 sm:pb-3 sm:pt-8">
        <form className="relative" onSubmit={onSubmit}>
          {closed ? (
            <p className="py-1 text-center text-sm text-muted-foreground">
              Incidente chiuso. Riaprilo per continuare la conversazione.
            </p>
          ) : (
            <>
              {activeMention && !streaming && (
                <div
                  role="listbox"
                  aria-label="Suggerimenti menzione"
                  className="absolute bottom-full left-0 mb-2 w-64 overflow-hidden rounded-lg border bg-background p-1 text-foreground shadow-xl"
                >
                  <button
                    type="button"
                    role="option"
                    aria-selected="true"
                    className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm hover:bg-accent focus:bg-accent focus:outline-none"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={completeMention}
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <Bot className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">@debrief</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        Chiedi aiuto all'assistente
                      </span>
                    </span>
                    <kbd className="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                      Tab
                    </kbd>
                  </button>
                </div>
              )}
              <div className="flex items-center gap-2 rounded-lg border bg-background/80 px-2.5 py-1.5 shadow-lg sm:px-3 sm:py-2">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value);
                    setCursorPosition(e.target.selectionStart);
                  }}
                  onSelect={(e) => setCursorPosition(e.currentTarget.selectionStart)}
                  onKeyDown={(e) => {
                    if (activeMention && (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey))) {
                      e.preventDefault();
                      completeMention();
                      return;
                    }
                    if (activeMention && e.key === "Escape") {
                      setCursorPosition(-1);
                      return;
                    }
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
            </>
          )}
        </form>
      </div>
    </div>
  );
}

function ToolBubble({ agent }: { agent: string | null }) {
  const identity = getAgentIdentity(agent ?? undefined);
  return (
    <div className="ml-10 flex">
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
  currentUserId,
}: {
  message: ChatMessage;
  incidentId: string;
  onOverrideConfirm: (msgId: number) => void;
  overridePending: boolean;
  currentUserId?: string;
}) {
  const [dismissed, setDismissed] = useState(message.overrideDismissed ?? false);
  const isUser = message.role === "user";
  const isOwn = isUser && message.senderId === currentUserId;
  const identity = getAgentIdentity(message.agent);
  return (
    <div className={cn("flex gap-2", isOwn ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "border border-border bg-muted text-muted-foreground" : identity.iconCls,
        )}
      >
        {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div
        className={cn(
          "max-w-[calc(100%-2.25rem)] space-y-2 sm:max-w-[80%]",
          isOwn ? "items-end" : "items-start",
        )}
      >
        {isUser && (
          <div className={cn("text-xs text-muted-foreground", isOwn && "text-right")}>
            <span className="font-medium text-foreground">{message.senderUsername}</span>
            {message.senderTeam && <> · {message.senderTeam}</>}
          </div>
        )}
        {!isUser && message.agent && message.agent !== "override" && (
          <div className="flex items-center gap-1.5 text-sm">
            <span className="font-medium text-foreground">{identity.label}</span>
            <span className="inline-flex h-4 items-center rounded-full bg-primary px-1.5 text-[9px] font-semibold leading-none tracking-wide text-primary-foreground">
              BOT
            </span>
          </div>
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
              "inline-block rounded-2xl px-3 py-2 text-sm shadow-sm",
              isUser
                ? cn(
                    "whitespace-pre-wrap border border-border bg-muted text-foreground",
                    isOwn ? "rounded-tr-sm" : "rounded-tl-sm",
                  )
                : cn("rounded-tl-sm", identity.bubbleCls),
            )}
          >
            {isUser ? (
              renderHumanMessage(message.content)
            ) : (
              <div className="prose prose-sm max-w-none leading-5 dark:prose-invert prose-headings:mb-1 prose-headings:mt-4 prose-headings:leading-tight prose-p:my-1 prose-p:leading-5 prose-blockquote:my-2 prose-code:text-sm prose-pre:my-1.5 prose-ol:my-1 prose-ol:pl-5 prose-ul:my-1 prose-ul:pl-5 prose-li:my-0 prose-li:leading-5 prose-table:my-2 prose-hr:my-3 [&>:first-child]:mt-0 [&_li+li]:mt-0.5 [&_li>p]:my-0">
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
