import { useId, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, Send } from "lucide-react";

import { SeverityBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useTeams } from "@/hooks/useTeams";
import type { TriageData } from "@/lib/types";

export function TriageCard({
  data,
  disabled = false,
  onSubmitClarifications,
}: {
  data: TriageData;
  disabled?: boolean;
  onSubmitClarifications?: (message: string) => Promise<boolean>;
}) {
  const { teamName } = useTeams();
  const confidence = Math.round(data.confidence * 100);
  const questions = data.clarifying_questions.filter((question) => question.trim().length > 0);
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ""));
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const answerIdPrefix = useId();
  const showClarifications =
    data.needs_clarification && questions.length > 0 && onSubmitClarifications !== undefined;

  function updateCurrentAnswer(value: string) {
    setAnswers((previous) =>
      previous.map((answer, index) => (index === currentQuestion ? value : answer)),
    );
  }

  async function submit(nextAnswers = answers) {
    if (!onSubmitClarifications) return;
    const message = [
      "Risposte ai chiarimenti richiesti dal triage:",
      ...questions.map(
        (question, index) =>
          `${index + 1}. ${question}\nRisposta: ${nextAnswers[index]?.trim() || "Non lo so"}`,
      ),
    ].join("\n\n");

    setSubmitting(true);
    try {
      const sent = await onSubmitClarifications(message);
      if (sent) setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  function continueWithoutAnswer() {
    const nextAnswers = answers.map((answer, index) =>
      index === currentQuestion ? "Non lo so" : answer,
    );
    setAnswers(nextAnswers);
    if (currentQuestion === questions.length - 1) void submit(nextAnswers);
    else setCurrentQuestion((question) => question + 1);
  }

  return (
    <div className="overflow-hidden rounded-2xl rounded-tl-sm border border-border bg-muted text-sm shadow-sm">
      <div className="p-3.5">
        <div className="mb-3 flex items-center gap-2.5 font-medium">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-border bg-background/70 text-muted-foreground">
            <ClipboardCheck className="h-4 w-4" />
          </span>
          <span>Classificazione triage</span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <SeverityBadge severity={data.severity} />
          <span className="text-xs font-medium text-muted-foreground">
            {confidence}% confidenza
          </span>
        </div>

        {data.suggested_teams.length > 0 && (
          <div className="mt-3 border-t border-border/70 pt-3">
            <div className="flex items-start gap-3">
              <span className="w-16 shrink-0 pt-1 text-xs font-medium text-muted-foreground">
                Team
              </span>
              <div className="flex flex-wrap gap-1.5">
                {data.suggested_teams.map((t) => (
                  <span
                    key={t}
                    className="rounded-md border border-border bg-background/75 px-2 py-0.5 text-xs font-medium"
                  >
                    {teamName(t)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {showClarifications && (
        <div className="border-t border-border p-3.5 sm:p-4">
          {submitted ? (
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              Risposte inviate al triage
            </div>
          ) : (
            <div className="space-y-3.5">
              <div>
                <div className="flex items-center justify-between gap-3 text-xs font-medium text-muted-foreground">
                  <span>Servono alcuni dettagli</span>
                  <span className="shrink-0 tabular-nums">
                    {currentQuestion + 1} di {questions.length}
                  </span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label
                  htmlFor={`${answerIdPrefix}-${currentQuestion}`}
                  className="block font-medium leading-snug"
                >
                  {questions[currentQuestion]}
                </label>
                <Textarea
                  key={currentQuestion}
                  id={`${answerIdPrefix}-${currentQuestion}`}
                  value={answers[currentQuestion] ?? ""}
                  onChange={(event) => updateCurrentAnswer(event.target.value)}
                  placeholder="Scrivi la risposta…"
                  rows={3}
                  disabled={disabled || submitting}
                  className="min-h-20 resize-y bg-background/85 shadow-none"
                  onKeyDown={(event) => {
                    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                      event.preventDefault();
                      if (!answers[currentQuestion]?.trim()) return;
                      if (currentQuestion === questions.length - 1) void submit();
                      else setCurrentQuestion((question) => question + 1);
                    }
                  }}
                />
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setCurrentQuestion((question) => question - 1)}
                  disabled={disabled || submitting || currentQuestion === 0}
                  className="w-full sm:w-auto"
                >
                  <ArrowLeft />
                  Indietro
                </Button>
                <div className="grid grid-cols-2 gap-2 sm:flex">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={continueWithoutAnswer}
                    disabled={disabled || submitting}
                  >
                    Non lo so
                  </Button>
                  {currentQuestion < questions.length - 1 ? (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => setCurrentQuestion((question) => question + 1)}
                      disabled={disabled || submitting || !answers[currentQuestion]?.trim()}
                    >
                      Avanti
                      <ArrowRight />
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void submit()}
                      disabled={disabled || submitting || !answers[currentQuestion]?.trim()}
                    >
                      <Send />
                      {submitting ? "Invio…" : "Invia risposte"}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
