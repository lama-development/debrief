import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Hash, Loader2, Search, Send, User as UserIcon } from "lucide-react";
import { toast } from "sonner";

import { OverrideConfirmCard } from "@/components/OverrideConfirmCard";
import { useAuth } from "@/auth/AuthContext";
import { TriageCard } from "@/components/TriageCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { hasAssistantEvents, useChatStream, type ChatMessage } from "@/hooks/useChatStream";
import { incidentsApi, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getAgentIdentity } from "@/lib/agents";
import type { HumanHelpRequest, IncidentStatus, TimelineEvent } from "@/lib/types";

const AssistantMarkdown = lazy(() => import("@/components/AssistantMarkdown"));

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

function formatMessageTime(timestamp: string) {
  const iso = timestamp.includes("T") ? timestamp : timestamp.replace(" ", "T") + "Z";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ChatPanel({
  incidentId,
  status,
  isSeedIncident = false,
  initialEvents,
  initialDraft = "",
  onIncidentChanged,
}: {
  incidentId: string;
  status: IncidentStatus;
  isSeedIncident?: boolean;
  initialEvents: TimelineEvent[];
  initialDraft?: string;
  onIncidentChanged: () => void;
}) {
  const { user } = useAuth();
  const { messages, streaming, toolActive, activeAgent, send, confirmOverride, cancelOverride } =
    useChatStream({ incidentId, status, initialEvents, user, onIncidentChanged });
  const [input, setInput] = useState("");
  const [cursorPosition, setCursorPosition] = useState(0);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autoSent = useRef(false);

  const closed = status === "resolved";
  const activeMention = mentionAtCursor(input, cursorPosition);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, toolActive]);

  // Avvia il triage al primo accesso a un incidente `open`.
  useEffect(() => {
    if (autoSent.current) return;
    if (status !== "open" || !initialDraft) return;
    if (hasAssistantEvents(initialEvents)) return;
    autoSent.current = true;
    void send(initialDraft);
  }, [initialDraft, initialEvents, send, status]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void sendMessage();
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

  function sendMessage(textArg?: string) {
    const text = (textArg ?? input).trim();
    if (!text || streaming) return Promise.resolve(false);
    if (textArg === undefined) setInput("");
    return send(text);
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
        {messages.length === 0 && isSeedIncident && (
          <p className="mt-8 text-center text-sm text-muted-foreground">
            {closed
              ? "Incidente importato. La conversazione originale non è disponibile. Consulta timeline e debriefing per i dettagli."
              : "Incidente importato. La conversazione precedente non è disponibile; puoi iniziarne una menzionando @debrief."}
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            incidentId={incidentId}
            onOverrideConfirm={confirmOverride}
            onOverrideCancel={cancelOverride}
            currentUserId={user?.id}
            clarificationsDisabled={streaming}
            onClarificationsSubmit={sendMessage}
          />
        ))}
        {toolActive && <ToolBubble agent={activeAgent} />}
      </div>

      {/* Campo di invio */}
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
                      void sendMessage();
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
    <div className="!-mt-1 ml-10 flex">
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
  onOverrideCancel,
  onClarificationsSubmit,
  clarificationsDisabled,
  currentUserId,
}: {
  message: ChatMessage;
  incidentId: string;
  onOverrideConfirm: (msgId: number) => void;
  onOverrideCancel: (msgId: number) => void;
  onClarificationsSubmit: (message: string) => Promise<boolean>;
  clarificationsDisabled: boolean;
  currentUserId?: string;
}) {
  const isUser = message.role === "user";
  const isOwn = isUser && message.senderId === currentUserId;
  const isFinalResolution = message.isFinalResolution === true;
  const identity = getAgentIdentity(message.agent);
  const overrideStatus = message.overrideStatus ?? "idle";
  const hasVisibleBubble = Boolean(
    message.content || message.triage || message.overrideProposal || message.humanHelp,
  );
  const hasGuidedClarifications = Boolean(
    message.triage?.needs_clarification &&
    message.triage.clarifying_questions.some((question) => question.trim().length > 0),
  );
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
        {message.triage && (
          <TriageCard
            data={message.triage}
            disabled={clarificationsDisabled}
            onSubmitClarifications={onClarificationsSubmit}
          />
        )}
        {message.overrideProposal &&
          (overrideStatus === "idle" || overrideStatus === "pending") && (
            <OverrideConfirmCard
              proposal={message.overrideProposal}
              isPending={overrideStatus === "pending"}
              onConfirm={() => onOverrideConfirm(message.id)}
              onCancel={() => onOverrideCancel(message.id)}
            />
          )}
        {message.overrideProposal && overrideStatus === "confirmed" && (
          <div className="inline-block rounded-2xl rounded-tl-sm bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-700 shadow-sm dark:text-emerald-400">
            Modifica applicata.
          </div>
        )}
        {message.overrideProposal && overrideStatus === "cancelled" && (
          <div className="inline-block rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm text-muted-foreground shadow-sm">
            Modifica annullata.
          </div>
        )}
        {message.humanHelp && <HumanHelpCard incidentId={incidentId} request={message.humanHelp} />}
        {message.content && !hasGuidedClarifications && (
          <div
            className={cn(
              "inline-block min-w-24 rounded-2xl px-3 py-2 text-sm shadow-sm",
              isUser
                ? cn(
                    "whitespace-pre-wrap",
                    isFinalResolution
                      ? "bg-emerald-500/10 font-medium text-emerald-700 dark:text-emerald-400"
                      : "border border-border bg-muted text-foreground",
                    isOwn ? "rounded-tr-sm" : "rounded-tl-sm",
                  )
                : cn("rounded-tl-sm", identity.bubbleCls),
            )}
          >
            {isUser ? (
              renderHumanMessage(message.content)
            ) : (
              <div className="prose prose-sm max-w-none leading-5 dark:prose-invert prose-headings:mb-1 prose-headings:mt-4 prose-headings:leading-tight prose-p:my-1 prose-p:leading-5 prose-blockquote:my-2 prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:font-mono prose-code:text-[0.85em] prose-code:before:content-none prose-code:after:content-none prose-pre:my-1.5 prose-ol:my-1 prose-ol:pl-5 prose-ul:my-1 prose-ul:pl-5 prose-li:my-0 prose-li:leading-5 prose-table:my-2 prose-hr:my-3 [&>:first-child]:mt-0 [&_li+li]:mt-0.5 [&_li>p]:my-0">
                <Suspense fallback={<div className="whitespace-pre-wrap">{message.content}</div>}>
                  <AssistantMarkdown content={message.content} />
                </Suspense>
              </div>
            )}
          </div>
        )}
        {hasVisibleBubble && (
          <div
            className={cn(
              "px-1 text-[10px] leading-none text-muted-foreground/70",
              isOwn && "text-right",
            )}
          >
            {formatMessageTime(message.timestamp)}
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
