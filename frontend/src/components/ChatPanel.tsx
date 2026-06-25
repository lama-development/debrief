import { useEffect, useRef, useState, type FormEvent } from "react"
import { Bot, Loader2, Search, Send, User as UserIcon } from "lucide-react"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { TriageCard } from "@/components/TriageCard"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { streamChat } from "@/lib/chat"
import { ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import { getAgentIdentity } from "@/lib/agents"
import type { ChatEvent, IncidentStatus, TimelineEvent, TriageData } from "@/lib/types"

interface ChatMessage {
  id: number
  role: "user" | "assistant"
  agent?: string
  content: string
  triage?: TriageData
}

const ASSISTANT_ACTORS = new Set(["triage", "investigator", "resolver"])
const CLOSED_STATUSES: IncidentStatus[] = ["resolved"]

// Costruisce la cronologia iniziale della chat dagli eventi di timeline.
function seedMessages(events: TimelineEvent[]): ChatMessage[] {
  const out: ChatMessage[] = []
  events.forEach((ev, idx) => {
    // idx 0 = dichiarazione dell'incidente (= la descrizione): è già mostrata
    // nella card "Descrizione" e nel milestone "Incidente dichiarato", quindi non
    // la ripetiamo come bolla di chat.
    if (idx === 0) return
    if (ev.event_type === "involvement") return // mostrato nella timeline a sinistra
    const isAssistant = ASSISTANT_ACTORS.has(ev.actor ?? "")
    out.push({
      id: ev.id,
      role: isAssistant ? "assistant" : "user",
      agent: isAssistant ? (ev.actor ?? undefined) : undefined,
      content: ev.content ?? "",
    })
  })
  return out
}

export function ChatPanel({
  incidentId,
  status,
  initialEvents,
  initialDraft = "",
  onTurnComplete,
}: {
  incidentId: string
  status: IncidentStatus
  initialEvents: TimelineEvent[]
  initialDraft?: string
  onTurnComplete: () => void
}) {
  // Seed una volta sola al mount (il parent passa key={incidentId} -> remount per incidente).
  const [messages, setMessages] = useState<ChatMessage[]>(() => seedMessages(initialEvents))
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [activeTool, setActiveTool] = useState<string | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)
  const nextLocalId = useRef(-1) // id negativi per i messaggi creati lato client
  const autoSent = useRef(false)

  const closed = CLOSED_STATUSES.includes(status)

  // Auto-scroll in fondo a ogni aggiornamento.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, activeTool])

  // Classificazione automatica: appena si apre un incidente "open" non ancora
  // gestito, avviamo da soli il triage sulla descrizione, nessun click richiesto.
  // (Il backend è pensato così: il primo messaggio di chat è la descrizione e il
  // router lo instrada al triage.)
  useEffect(() => {
    if (autoSent.current) return
    if (status !== "open" || !initialDraft) return
    if (initialEvents.some((e) => ASSISTANT_ACTORS.has(e.actor ?? ""))) return
    autoSent.current = true
    void send(initialDraft)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send()
  }

  // textArg valorizzato = invio automatico (es. auto-triage); undefined = dall'input utente.
  async function send(textArg?: string) {
    const text = (textArg ?? input).trim()
    if (!text || streaming) return

    const userMsg: ChatMessage = { id: nextLocalId.current--, role: "user", content: text }
    // Messaggio assistente "in costruzione" che riempiremo coi token in streaming.
    const assistantId = nextLocalId.current--
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "" }])
    if (textArg === undefined) setInput("")
    setStreaming(true)
    setActiveTool(null)

    // Aggiorna il messaggio assistente corrente in modo immutabile.
    const patchAssistant = (patch: Partial<ChatMessage>) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, ...patch, content: patch.content ?? m.content } : m)),
      )
    const appendToken = (token: string) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m)),
      )

    const onEvent = (ev: ChatEvent) => {
      switch (ev.type) {
        case "routing":
          patchAssistant({ agent: ev.agent })
          break
        case "tool":
          setActiveTool(ev.name)
          break
        case "triage":
          patchAssistant({ agent: "triage", triage: ev.data })
          break
        case "token":
          appendToken(ev.content)
          break
        case "done":
          setActiveTool(null)
          onTurnComplete()
          break
        case "error":
          toast.error(ev.message)
          appendToken(`\n\n[errore: ${ev.message}]`)
          break
      }
    }

    try {
      await streamChat(incidentId, text, onEvent)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Errore durante la chat")
      patchAssistant({ content: "Si è verificato un errore. Riprova." })
    } finally {
      setStreaming(false)
      setActiveTool(null)
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
          <MessageBubble key={m.id} message={m} />
        ))}
        {activeTool && (
          <div className="flex items-center gap-2 pl-10 text-sm text-muted-foreground">
            <Search className="h-3.5 w-3.5 animate-pulse" /> ricerca in corso ({activeTool})…
          </div>
        )}
      </div>

      {/* Input floating */}
      <div className="absolute bottom-0 left-0 right-0 px-3 pb-3 pt-8 bg-gradient-to-t from-background via-background/80 via-60% to-transparent">
        <form onSubmit={onSubmit}>
          {closed ? (
            <p className="text-center text-sm text-muted-foreground py-1">
              Incidente chiuso. Riaprilo per continuare la conversazione.
            </p>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border bg-background/80 shadow-lg px-3 py-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    void send()
                  }
                }}
                placeholder="Scrivi un messaggio…"
                rows={1}
                className="min-h-[32px] resize-none border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent p-0"
                disabled={streaming}
              />
              <Button type="submit" size="icon" className="shrink-0 h-8 w-8" disabled={streaming || !input.trim()}>
                {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"
  const identity = getAgentIdentity(message.agent)
  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary/15 text-foreground ring-1 ring-inset ring-primary/20" : identity.iconCls,
        )}
      >
        {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={cn("max-w-[80%] space-y-2", isUser ? "items-end" : "items-start")}>
        {!isUser && message.agent && (
          <div className="text-sm font-medium text-muted-foreground">
            {identity.label}
          </div>
        )}
        {message.triage && <TriageCard data={message.triage} />}
        {message.content && (
          <div
            className={cn(
              "inline-block rounded-lg px-3 py-2 text-sm shadow-sm",
              isUser
                ? "whitespace-pre-wrap bg-primary/15 text-foreground border border-primary/30"
                : identity.bubbleCls,
            )}
          >
            {isUser ? (
              message.content
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2 prose-pre:my-1 prose-code:text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
