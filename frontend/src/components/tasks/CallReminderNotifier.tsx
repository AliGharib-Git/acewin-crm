import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { PhoneCall, BellRing } from "lucide-react";
import { tasksApi } from "../../api/tasks";
import { useLanguage } from "../../context/LanguageContext";

const NOTIFIED_STORAGE_KEY = "acewin-notified-reminders";
const POLL_INTERVAL_MS = 30_000;

function loadNotifiedIds(): Set<number> {
  try {
    const raw = window.localStorage.getItem(NOTIFIED_STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function saveNotifiedIds(ids: Set<number>) {
  window.localStorage.setItem(NOTIFIED_STORAGE_KEY, JSON.stringify(Array.from(ids)));
}

/**
 * Mounted once (in Layout) while the user is logged in. Polls pending "call"
 * type tasks and fires a browser notification (falling back to an in-app
 * toast) once each reminder's "remind me before" window is reached.
 */
export function CallReminderNotifier() {
  const { t } = useLanguage();
  const notifiedRef = useRef<Set<number>>(loadNotifiedIds());
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification !== "undefined" ? Notification.permission : "unsupported"
  );
  const [dismissedPrompt, setDismissedPrompt] = useState(false);

  const { data } = useQuery({
    queryKey: ["tasks", "call-reminders"],
    queryFn: () => tasksApi.list({ task_type: "call", status: "pending", page_size: 200 }),
    refetchInterval: POLL_INTERVAL_MS,
  });

  useEffect(() => {
    if (!data) return;
    const now = Date.now();

    for (const task of data.items) {
      if (!task.due_date || notifiedRef.current.has(task.id)) continue;
      const dueMs = new Date(task.due_date).getTime();
      const leadMs = (task.reminder_minutes_before ?? 0) * 60_000;
      const notifyAtMs = dueMs - leadMs;

      // Fire once we've reached the notify window, but skip stale reminders
      // that are more than a day overdue so old demo data doesn't spam on load.
      if (now >= notifyAtMs && now - dueMs < 24 * 60 * 60_000) {
        const title = t("tasks.notifyBody");
        const body = task.contact_name
          ? t("tasks.callWith", { name: task.contact_name })
          : task.title;

        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          try {
            new Notification(title, { body, tag: `call-reminder-${task.id}` });
          } catch {
            toast(body, { icon: "📞" });
          }
        } else {
          toast(body, { icon: "📞" });
        }

        notifiedRef.current.add(task.id);
        saveNotifiedIds(notifiedRef.current);
      }
    }
  }, [data, t]);

  async function requestPermission() {
    if (typeof Notification === "undefined") return;
    const result = await Notification.requestPermission();
    setPermission(result);
    setDismissedPrompt(true);
  }

  const shouldPromptForPermission =
    permission === "default" && !dismissedPrompt && (data?.items.length ?? 0) > 0;

  if (!shouldPromptForPermission) return null;

  return (
    <div className="fixed bottom-4 start-4 z-50 flex max-w-sm items-start gap-3 rounded border border-border bg-surface p-4 shadow-card">
      <BellRing className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
      <div className="flex-1 text-sm">
        <p className="text-ink">{t("tasks.notifyPermissionAsk")}</p>
        <div className="mt-2 flex gap-2">
          <button
            onClick={requestPermission}
            className="flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-xs font-medium text-black hover:bg-primary-dark"
          >
            <PhoneCall className="h-3.5 w-3.5" />
            {t("tasks.notifyEnable")}
          </button>
          <button
            onClick={() => setDismissedPrompt(true)}
            className="rounded px-2.5 py-1 text-xs font-medium text-muted hover:bg-paper"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
