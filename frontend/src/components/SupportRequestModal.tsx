import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Clock, MessageCircle } from "lucide-react";
import { Button, Input, Modal, Textarea } from "./ui";
import { supportRequestsApi } from "../api/supportRequests";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { SupportRequestStatus } from "../types";

function StatusPill({ status }: { status: SupportRequestStatus }) {
  const { language } = useLanguage();
  const fa = language === "fa";
  const map: Record<SupportRequestStatus, { label: string; color: string }> = {
    open: { label: fa ? "در انتظار" : "Open", color: "#93A6A6" },
    in_progress: { label: fa ? "در حال بررسی" : "In progress", color: "#F2A93B" },
    resolved: { label: fa ? "پاسخ داده شد" : "Resolved", color: "#14D9A6" },
  };
  const { label, color } = map[status];
  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}22`, color }}
    >
      {label}
    </span>
  );
}

/** "Contact support" -- any signed-in user can ask the Platform Admin
 * for anything: a bug, a feature, a question, whatever they need. Filing
 * one notifies the admin (email + the Platform Admin panel's Requests
 * tab -- see backend app/routers/support_requests.py) and the requester
 * can track its status/reply right here. */
export function SupportRequestModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { language } = useLanguage();
  const fa = language === "fa";
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const { data: requests, isLoading } = useQuery({
    queryKey: ["my-support-requests"],
    queryFn: supportRequestsApi.list,
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: () => supportRequestsApi.create({ subject, message }),
    onSuccess: () => {
      setSubject("");
      setMessage("");
      queryClient.invalidateQueries({ queryKey: ["my-support-requests"] });
      toast.success(fa ? "درخواست شما برای ادمین ارسال شد" : "Your request was sent to the admin");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function submit() {
    if (!subject.trim() || !message.trim()) return;
    createMutation.mutate();
  }

  return (
    <Modal open={open} onClose={onClose} title={fa ? "درخواست از ادمین / پشتیبانی" : "Contact admin / support"} size="md">
      <div className="space-y-6">
        <section className="space-y-3">
          <p className="text-sm text-muted">
            {fa
              ? "هر چیزی نیاز دارید -- گزارش مشکل، درخواست امکان جدید، یا هر سوالی -- اینجا بنویسید. مستقیم به ادمین اطلاع داده می‌شود."
              : "Whatever you need -- a bug report, a feature request, or any question -- write it here. The admin is notified directly."}
          </p>
          <Input
            label={fa ? "موضوع" : "Subject"}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder={fa ? "مثلاً: نیاز به گزارش سفارشی" : "e.g. Need a custom report"}
          />
          <Textarea
            label={fa ? "پیام" : "Message"}
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={fa ? "جزئیات درخواست خود را بنویسید…" : "Describe what you need…"}
          />
          <Button isLoading={createMutation.isPending} onClick={submit} disabled={!subject.trim() || !message.trim()}>
            <MessageCircle className="h-4 w-4" />
            {fa ? "ارسال درخواست" : "Send request"}
          </Button>
        </section>

        <section>
          <h3 className="mb-2 flex items-center gap-2 font-display text-sm font-medium text-ink">
            <Clock className="h-4 w-4 text-primary" />
            {fa ? "درخواست‌های قبلی من" : "My previous requests"}
          </h3>
          {isLoading ? (
            <p className="text-sm text-muted">{fa ? "در حال بارگذاری…" : "Loading…"}</p>
          ) : !requests || requests.length === 0 ? (
            <p className="text-sm text-muted">{fa ? "هنوز درخواستی ثبت نکرده‌اید." : "You haven't filed a request yet."}</p>
          ) : (
            <div className="space-y-3">
              {requests.map((r) => (
                <div key={r.id} className="rounded border border-border p-3">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">{r.subject}</span>
                    <StatusPill status={r.status} />
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-muted">{r.message}</p>
                  {r.admin_reply && (
                    <div className="mt-2 rounded bg-primary/10 p-2 text-sm text-ink">
                      <span className="font-medium text-primary">{fa ? "پاسخ ادمین: " : "Admin reply: "}</span>
                      {r.admin_reply}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </Modal>
  );
}
