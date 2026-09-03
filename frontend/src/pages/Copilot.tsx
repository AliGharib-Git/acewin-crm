import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, ChevronDown, Send, Sparkles, Undo2, User as UserIcon, Wrench } from "lucide-react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { Button, Card } from "../components/ui";
import { copilotApi } from "../api/copilot";
import { agentActionsApi } from "../api/agentActions";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { CopilotAnswer, CopilotMessage } from "../types";

const SUGGESTIONS = {
  en: ["Show today's priorities", "Which customers have not purchased in 30 days?", "Which customers are at risk of churning?", "Generate this month's sales summary"],
  fa: ["اولویت‌های امروز را نشان بده", "کدام مشتریان ۳۰ روز است خرید نکرده‌اند؟", "کدام مشتریان در معرض ریزش هستند؟", "خلاصهٔ فروش این ماه را تولید کن"],
};

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const color = pct >= 70 ? "#14D9A6" : pct >= 40 ? "#22F0C2" : "#F2555B";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="font-mono text-xs text-muted">{pct}%</span>
    </div>
  );
}

function UndoButton({ actionLogId, language }: { actionLogId: number; language: "en" | "fa" }) {
  const fa = language === "fa";
  const [state, setState] = useState<"idle" | "done">("idle");

  const mutation = useMutation({
    mutationFn: () => agentActionsApi.undo(actionLogId),
    onSuccess: () => {
      setState("done");
      toast.success(fa ? "این اقدام واگرد شد." : "Action undone.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (state === "done") {
    return <span className="text-[11px] font-medium text-muted">{fa ? "واگرد شد" : "Undone"}</span>;
  }

  return (
    <button
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] font-medium text-ink hover:border-accent hover:text-accent disabled:opacity-50"
    >
      <Undo2 className="h-3 w-3" />
      {mutation.isPending ? (fa ? "در حال واگرد…" : "Undoing…") : fa ? "واگرد این اقدام" : "Undo"}
    </button>
  );
}

function ToolTrace({ answer, language }: { answer: CopilotAnswer; language: "en" | "fa" }) {
  const fa = language === "fa";
  const [open, setOpen] = useState(false);
  if (!answer.tool_calls.length) return null;
  return (
    <div className="mt-3 border-t border-border pt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink"
      >
        <Wrench className="h-3.5 w-3.5" />
        {answer.tool_calls.length} tool call{answer.tool_calls.length > 1 ? "s" : ""}
        <ChevronDown className={clsx("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {answer.tool_calls.map((call, i) => {
            const actionLogId = call.result?.action_log_id;
            return (
              <div key={i} className="rounded border border-border bg-paper p-2 font-mono text-[11px]">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-ink">{call.tool_name}</div>
                  {typeof actionLogId === "number" && <UndoButton actionLogId={actionLogId} language={language} />}
                </div>
                {Object.keys(call.arguments).length > 0 && (
                  <div className="mt-0.5 text-muted">args: {JSON.stringify(call.arguments)}</div>
                )}
                <div className="mt-0.5 max-h-24 overflow-y-auto text-muted">{JSON.stringify(call.result)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AnswerCard({ answer, language }: { answer: CopilotAnswer; language: "en" | "fa" }) {
  const fa = language === "fa";
  return (
    <Card className="p-4">
      {!answer.is_connected && (
        <div className="mb-3 rounded bg-accent/10 px-3 py-2 text-xs font-medium text-accent">
          {fa ? "دستیار هنوز به ارائه‌دهندهٔ هوش مصنوعی وصل نیست؛ AI_PROVIDER=avalai و AI_API_KEY را در backend/.env تنظیم کنید." : "Copilot isn't connected to an AI provider yet — set AI_PROVIDER=avalai and AI_API_KEY in backend/.env."}
        </div>
      )}
      <p className="text-sm font-medium text-ink">{answer.summary}</p>
      <dl className="mt-3 space-y-2 text-sm">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{fa ? "تحلیل" : "Analysis"}</dt>
          <dd className="mt-0.5 text-ink/90">{answer.analysis}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{fa ? "پیشنهاد" : "Recommendation"}</dt>
          <dd className="mt-0.5 text-ink/90">{answer.recommendation}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{fa ? "اثر کسب‌وکار" : "Business impact"}</dt>
          <dd className="mt-0.5 text-ink/90">{answer.business_impact}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{fa ? "اقدام بعدی" : "Next action"}</dt>
          <dd className="mt-0.5 text-ink/90">{answer.next_action}</dd>
        </div>
      </dl>
      <div className="mt-3 flex items-center justify-between border-t border-border pt-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{fa ? "اطمینان" : "Confidence"}</span>
        <ConfidenceBar score={answer.confidence_score} />
      </div>
      <ToolTrace answer={answer} language={language} />
    </Card>
  );
}

export default function Copilot() {
  const { t, language } = useLanguage();
  const fa = language === "fa";
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const listEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow the composer with the text (up to a cap) instead of staying
  // pinned at a single cramped line.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const mutation = useMutation({
    mutationFn: (query: string) => copilotApi.ask(query, language),
  });

  const isEmpty = useMemo(() => messages.length === 0, [messages]);

  function send(query: string) {
    const trimmed = query.trim();
    if (!trimmed || mutation.isPending) return;
    const userMsg: CopilotMessage = { id: crypto.randomUUID(), role: "user", query: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    mutation.mutate(trimmed, {
      onSuccess: (answer) => {
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", answer }]);
        setTimeout(() => listEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
      },
      onError: (err) => {
        const message = errorMessage(err);
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            answer: {
              summary: language === "fa" ? "خطایی رخ داد." : "Something went wrong.",
              analysis: message,
              recommendation: language === "fa" ? "چند لحظه بعد دوباره تلاش کنید." : "Try again in a moment.",
              confidence_score: 0,
              business_impact: language === "fa" ? "پاسخی تولید نشد." : "No answer produced.",
              next_action: language === "fa" ? "سؤال خود را دوباره ارسال کنید." : "Retry your question.",
              tool_calls: [],
              is_connected: false,
            },
          },
        ]);
      },
    });
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col">
      <div>
        <h1 className="flex items-center gap-2 font-display text-2xl font-medium text-ink">
          <Sparkles className="h-5 w-5 text-primary" />
          {t("nav.copilot")}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("copilot.pageDescription")}</p>
      </div>

      <div className="mt-4 flex-1 overflow-y-auto pe-1">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <Bot className="h-10 w-10 text-muted" />
            <p className="max-w-sm text-sm text-muted">{t("copilot.emptyStateHint")}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS[language].map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:border-primary hover:text-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 pb-2">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end gap-2">
                  <div className="max-w-lg rounded-lg bg-primary px-3 py-2 text-sm text-white">{m.query}</div>
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
                    <UserIcon className="h-4 w-4 text-ink" />
                  </div>
                </div>
              ) : (
                <div key={m.id} className="flex gap-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                  <div className="max-w-2xl flex-1">{m.answer && <AnswerCard answer={m.answer} language={language} />}</div>
                </div>
              )
            )}
            {mutation.isPending && (
              <div className="flex gap-2">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <Card className="px-3 py-2 text-sm text-muted">Thinking…</Card>
              </div>
            )}
            <div ref={listEndRef} />
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-3 border-t border-border pt-3"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface px-3 py-2 shadow-sm transition-colors focus-within:border-primary focus-within:ring-1 focus-within:ring-primary">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            placeholder={fa ? "از دستیار ACEWIN بپرس…" : "Ask the ACEWIN Copilot…"}
            rows={1}
            className="max-h-40 min-h-[28px] flex-1 resize-none border-0 bg-transparent py-1.5 text-sm leading-relaxed text-ink placeholder:text-muted/70 focus:outline-none focus:ring-0"
          />
          <Button type="submit" isLoading={mutation.isPending} disabled={!input.trim()} className="shrink-0 rounded-xl">
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1.5 px-1 text-[11px] text-muted">
          {fa ? "برای ارسال Enter و برای خط جدید Shift+Enter را بزنید" : "Press Enter to send, Shift+Enter for a new line"}
        </p>
      </form>
    </div>
  );
}
