import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { ShieldCheck, ShieldOff, Settings2, Building2, Inbox, History, MessageSquare } from "lucide-react";
import { Card, Button, Input, Select, Textarea, PageSpinner, StatusBadge, Badge, Modal } from "../components/ui";
import { platformAdminApi } from "../api/platformAdmin";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type {
  PlanTier,
  PlatformFeedback,
  PlatformOrganization,
  PlatformSupportRequest,
  SubscriptionStatus,
  SupportRequestStatus,
} from "../types";

const PLAN_TIERS: PlanTier[] = ["basic", "pro", "vip"];
const SUB_STATUSES: SubscriptionStatus[] = ["pending_trial", "trialing", "active", "past_due", "canceled"];

function OrgEditModal({ org, onClose }: { org: PlatformOrganization; onClose: () => void }) {
  const { language } = useLanguage();
  const fa = language === "fa";
  const queryClient = useQueryClient();

  const [plan, setPlan] = useState<PlanTier>(org.plan);
  const [status, setStatus] = useState<SubscriptionStatus>(org.status);
  const [limitOverrides, setLimitOverrides] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(org.limit_overrides).map(([k, v]) => [k, String(v)]))
  );
  const [newMetric, setNewMetric] = useState("ai_requests_per_month");
  const [newMetricValue, setNewMetricValue] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["platform-admin-orgs"] });

  const subscriptionMutation = useMutation({
    mutationFn: () => platformAdminApi.updateSubscription(org.id, { plan, status }),
    onSuccess: () => {
      invalidate();
      toast.success(fa ? "اشتراک بروزرسانی شد" : "Subscription updated");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const approveTrialMutation = useMutation({
    mutationFn: () => platformAdminApi.approveTrial(org.id),
    onSuccess: (data) => {
      invalidate();
      setStatus(data.status);
      toast.success(fa ? "دورهٔ آزمایشی ۱۴ روزه فعال شد" : "14-day trial activated");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const limitsMutation = useMutation({
    mutationFn: (overrides: Record<string, number>) => platformAdminApi.updateLimitOverrides(org.id, overrides),
    onSuccess: (data) => {
      invalidate();
      setLimitOverrides(Object.fromEntries(Object.entries(data.limit_overrides).map(([k, v]) => [k, String(v)])));
      toast.success(fa ? "محدودیت‌ها ذخیره شد" : "Limits saved");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function saveLimits() {
    const overrides: Record<string, number> = {};
    for (const [k, v] of Object.entries(limitOverrides)) {
      if (v.trim() === "") continue;
      const n = Number(v);
      if (!Number.isNaN(n)) overrides[k] = n;
    }
    limitsMutation.mutate(overrides);
  }

  function addOverride() {
    if (!newMetric || newMetricValue.trim() === "") return;
    setLimitOverrides((prev) => ({ ...prev, [newMetric]: newMetricValue }));
    setNewMetricValue("");
  }

  function removeOverride(metric: string) {
    setLimitOverrides((prev) => {
      const next = { ...prev };
      delete next[metric];
      return next;
    });
  }

  return (
    <Modal open onClose={onClose} title={org.name} size="md">
      <div className="space-y-6">
        {org.status === "pending_trial" && (
          <section className="rounded border border-primary/30 bg-primary/5 p-3">
            <h3 className="font-display text-sm font-medium text-ink">
              {fa ? "درخواست دورهٔ آزمایشی در انتظار بررسی" : "Trial request awaiting review"}
            </h3>
            <p className="mt-1 text-xs text-muted">
              {fa
                ? "این شرکت همین الان ثبت‌نام کرده و منتظر تأیید شماست تا دورهٔ آزمایشی ۱۴ روزهٔ پلن پایه‌اش شروع شود."
                : "This company just registered and is waiting for your approval to start its 14-day Basic trial."}
            </p>
            <div className="mt-2">
              <Button size="sm" isLoading={approveTrialMutation.isPending} onClick={() => approveTrialMutation.mutate()}>
                {fa ? "تأیید و شروع دورهٔ آزمایشی" : "Approve & start trial"}
              </Button>
            </div>
          </section>
        )}

        <section>
          <h3 className="mb-2 font-display text-sm font-medium text-ink">
            {fa ? "پلن و وضعیت اشتراک" : "Plan & subscription status"}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <Select label={fa ? "پلن" : "Plan"} value={plan} onChange={(e) => setPlan(e.target.value as PlanTier)}>
              {PLAN_TIERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
            <Select
              label={fa ? "وضعیت" : "Status"}
              value={status}
              onChange={(e) => setStatus(e.target.value as SubscriptionStatus)}
            >
              {SUB_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
          <div className="mt-3">
            <Button size="sm" isLoading={subscriptionMutation.isPending} onClick={() => subscriptionMutation.mutate()}>
              {fa ? "ذخیره پلن و وضعیت" : "Save plan & status"}
            </Button>
          </div>
        </section>

        <section>
          <h3 className="mb-2 font-display text-sm font-medium text-ink">
            {fa ? "محدودیت‌های اختصاصی (مثلاً تعداد سوالات دستیار هوشمند)" : "Custom limits (e.g. Copilot question quota)"}
          </h3>
          <p className="mb-3 text-xs text-muted">
            {fa
              ? "این مقادیر جایگزین سقف پلن برای همین شرکت می‌شوند. برای بازگشت به سقف پیش‌فرض پلن، آن را حذف کنید."
              : "These values override the plan's ceiling for this company only. Remove one to fall back to the plan default."}
          </p>
          <div className="space-y-2">
            {Object.entries(limitOverrides).map(([metric, value]) => (
              <div key={metric} className="flex items-center gap-2">
                <span className="w-48 shrink-0 text-sm text-ink">{metric}</span>
                <Input
                  className="flex-1"
                  value={value}
                  onChange={(e) => setLimitOverrides((prev) => ({ ...prev, [metric]: e.target.value }))}
                />
                <Button variant="ghost" size="sm" onClick={() => removeOverride(metric)}>
                  {fa ? "حذف" : "Remove"}
                </Button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Select className="w-56" value={newMetric} onChange={(e) => setNewMetric(e.target.value)}>
              <option value="ai_requests_per_month">ai_requests_per_month</option>
              <option value="users">users</option>
              <option value="contacts">contacts</option>
              <option value="companies">companies</option>
              <option value="deals">deals</option>
            </Select>
            <Input
              className="w-32"
              placeholder={fa ? "مقدار" : "value"}
              value={newMetricValue}
              onChange={(e) => setNewMetricValue(e.target.value)}
            />
            <Button variant="secondary" size="sm" onClick={addOverride}>
              {fa ? "افزودن" : "Add"}
            </Button>
          </div>
          <div className="mt-3">
            <Button size="sm" isLoading={limitsMutation.isPending} onClick={saveLimits}>
              {fa ? "ذخیره محدودیت‌ها" : "Save limits"}
            </Button>
          </div>
        </section>
      </div>
    </Modal>
  );
}

function ReplyModal({ request, onClose }: { request: PlatformSupportRequest; onClose: () => void }) {
  const { language } = useLanguage();
  const fa = language === "fa";
  const queryClient = useQueryClient();
  const [reply, setReply] = useState(request.admin_reply ?? "");
  const [status, setStatus] = useState<SupportRequestStatus>(request.status);

  const mutation = useMutation({
    mutationFn: () => platformAdminApi.updateRequest(request.id, { status, admin_reply: reply }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-requests"] });
      toast.success(fa ? "پاسخ ذخیره شد" : "Reply saved");
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal open onClose={onClose} title={request.subject} size="md">
      <div className="space-y-4">
        <div className="rounded border border-border p-3 text-sm">
          <div className="mb-1 text-xs text-muted">
            {request.organization_name} — {request.user_name} ({request.user_email})
          </div>
          <p className="whitespace-pre-wrap text-ink">{request.message}</p>
        </div>
        <Select label={fa ? "وضعیت" : "Status"} value={status} onChange={(e) => setStatus(e.target.value as SupportRequestStatus)}>
          <option value="open">{fa ? "در انتظار" : "Open"}</option>
          <option value="in_progress">{fa ? "در حال بررسی" : "In progress"}</option>
          <option value="resolved">{fa ? "پاسخ داده شد" : "Resolved"}</option>
        </Select>
        <Textarea
          label={fa ? "پاسخ شما" : "Your reply"}
          rows={4}
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder={fa ? "پاسخ خود را برای کاربر بنویسید…" : "Write a reply the user will see…"}
        />
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          {fa ? "ذخیره" : "Save"}
        </Button>
      </div>
    </Modal>
  );
}

function FeedbackReplyModal({ feedback, onClose }: { feedback: PlatformFeedback; onClose: () => void }) {
  const { language } = useLanguage();
  const fa = language === "fa";
  const queryClient = useQueryClient();
  const [reply, setReply] = useState(feedback.admin_reply ?? "");
  const [status, setStatus] = useState<SupportRequestStatus>(feedback.status);

  const mutation = useMutation({
    mutationFn: () => platformAdminApi.updateFeedback(feedback.id, { status, admin_reply: reply }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-feedback"] });
      toast.success(fa ? "پاسخ ذخیره شد" : "Reply saved");
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const categoryLabel: Record<PlatformFeedback["category"], string> = {
    suggestion: fa ? "پیشنهاد" : "Suggestion",
    complaint: fa ? "انتقاد" : "Complaint",
    question: fa ? "سوال" : "Question",
  };

  return (
    <Modal open onClose={onClose} title={`${categoryLabel[feedback.category]} — ${feedback.name}`} size="md">
      <div className="space-y-4">
        <div className="rounded border border-border p-3 text-sm">
          <div className="mb-1 text-xs text-muted">{feedback.name} {feedback.email ? `(${feedback.email})` : ""}</div>
          <p className="whitespace-pre-wrap text-ink">{feedback.message}</p>
        </div>
        <Select label={fa ? "وضعیت" : "Status"} value={status} onChange={(e) => setStatus(e.target.value as SupportRequestStatus)}>
          <option value="open">{fa ? "در انتظار" : "Open"}</option>
          <option value="in_progress">{fa ? "در حال بررسی" : "In progress"}</option>
          <option value="resolved">{fa ? "پاسخ داده شد" : "Resolved"}</option>
        </Select>
        <Textarea
          label={fa ? "پاسخ شما" : "Your reply"}
          rows={4}
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder={fa ? "پاسخ خود را بنویسید…" : "Write a reply…"}
        />
        <Button isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          {fa ? "ذخیره" : "Save"}
        </Button>
      </div>
    </Modal>
  );
}

function FeedbackTab() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const [statusFilter, setStatusFilter] = useState<SupportRequestStatus | "">("");
  const [replying, setReplying] = useState<PlatformFeedback | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ["platform-admin-feedback", statusFilter],
    queryFn: () => platformAdminApi.listFeedback(statusFilter || undefined),
  });

  const categoryLabel: Record<PlatformFeedback["category"], string> = {
    suggestion: fa ? "پیشنهاد" : "Suggestion",
    complaint: fa ? "انتقاد" : "Complaint",
    question: fa ? "سوال" : "Question",
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        {fa
          ? "نظرات و انتقاداتی که بازدیدکنندگان از صفحه‌ی اصلی سایت ثبت می‌کنند، اینجا نمایش داده می‌شود و همزمان به ایمیل ادمین هم ارسال شده است."
          : "Comments and complaints visitors submit from the site's homepage show up here, and were already emailed to the admin."}
      </p>
      <Select className="w-56" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as SupportRequestStatus | "")}>
        <option value="">{fa ? "همه وضعیت‌ها" : "All statuses"}</option>
        <option value="open">{fa ? "در انتظار" : "Open"}</option>
        <option value="in_progress">{fa ? "در حال بررسی" : "In progress"}</option>
        <option value="resolved">{fa ? "پاسخ داده شد" : "Resolved"}</option>
      </Select>

      {isLoading ? (
        <PageSpinner />
      ) : !items || items.length === 0 ? (
        <p className="text-sm text-muted">{fa ? "هنوز نظری ثبت نشده است." : "No feedback filed yet."}</p>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-start text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 text-start">{fa ? "نام / ایمیل" : "Name / email"}</th>
                <th className="px-4 py-3 text-start">{fa ? "نوع" : "Category"}</th>
                <th className="px-4 py-3 text-start">{fa ? "پیام" : "Message"}</th>
                <th className="px-4 py-3 text-start">{fa ? "وضعیت" : "Status"}</th>
                <th className="px-4 py-3 text-start">{fa ? "تاریخ" : "Date"}</th>
                <th className="px-4 py-3 text-start">{fa ? "عملیات" : "Actions"}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((f) => (
                <tr key={f.id} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">{f.name}</div>
                    <div className="text-xs text-muted">{f.email ?? "-"}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{categoryLabel[f.category]}</Badge>
                  </td>
                  <td className="max-w-xs truncate px-4 py-3">{f.message}</td>
                  <td className="px-4 py-3">
                    <StatusBadge value={f.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">{new Date(f.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <Button variant="secondary" size="sm" onClick={() => setReplying(f)}>
                      {fa ? "پاسخ / مدیریت" : "Reply / manage"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {replying && <FeedbackReplyModal feedback={replying} onClose={() => setReplying(null)} />}
    </div>
  );
}

function RequestsTab() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const [subTab, setSubTab] = useState<"requests" | "feedback" | "actions">("requests");
  const [statusFilter, setStatusFilter] = useState<SupportRequestStatus | "">("");
  const [replying, setReplying] = useState<PlatformSupportRequest | null>(null);

  const { data: requests, isLoading: requestsLoading } = useQuery({
    queryKey: ["platform-admin-requests", statusFilter],
    queryFn: () => platformAdminApi.listRequests(statusFilter || undefined),
    enabled: subTab === "requests",
  });

  const { data: actionsPage, isLoading: actionsLoading } = useQuery({
    queryKey: ["platform-admin-actions"],
    queryFn: () => platformAdminApi.listActions({ page: 1, page_size: 50 }),
    enabled: subTab === "actions",
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-border">
        <button
          onClick={() => setSubTab("requests")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            subTab === "requests" ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <Inbox className="h-4 w-4" />
          {fa ? "درخواست‌های کاربران" : "User requests"}
        </button>
        <button
          onClick={() => setSubTab("feedback")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            subTab === "feedback" ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          {fa ? "نظرات و انتقادات" : "Feedback"}
        </button>
        <button
          onClick={() => setSubTab("actions")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            subTab === "actions" ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <History className="h-4 w-4" />
          {fa ? "فید اکشن‌ها (خودکار)" : "Action feed (automatic)"}
        </button>
      </div>

      {subTab === "feedback" && <FeedbackTab />}

      {subTab === "requests" && (
        <div className="space-y-3">
          <Select
            className="w-56"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as SupportRequestStatus | "")}
          >
            <option value="">{fa ? "همه وضعیت‌ها" : "All statuses"}</option>
            <option value="open">{fa ? "در انتظار" : "Open"}</option>
            <option value="in_progress">{fa ? "در حال بررسی" : "In progress"}</option>
            <option value="resolved">{fa ? "پاسخ داده شد" : "Resolved"}</option>
          </Select>

          {requestsLoading ? (
            <PageSpinner />
          ) : !requests || requests.length === 0 ? (
            <p className="text-sm text-muted">{fa ? "درخواستی ثبت نشده است." : "No requests filed yet."}</p>
          ) : (
            <Card className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-start text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 text-start">{fa ? "شرکت / کاربر" : "Company / user"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "موضوع" : "Subject"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "وضعیت" : "Status"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "تاریخ" : "Date"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "عملیات" : "Actions"}</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((r) => (
                    <tr key={r.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3">
                        <div className="font-medium text-ink">{r.organization_name}</div>
                        <div className="text-xs text-muted">{r.user_name}</div>
                      </td>
                      <td className="max-w-xs truncate px-4 py-3">{r.subject}</td>
                      <td className="px-4 py-3">
                        <StatusBadge value={r.status} />
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">{new Date(r.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <Button variant="secondary" size="sm" onClick={() => setReplying(r)}>
                          {fa ? "پاسخ / مدیریت" : "Reply / manage"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {subTab === "actions" && (
        <div className="space-y-3">
          <p className="text-xs text-muted">
            {fa
              ? "هر کاری که هر کاربری در هر شرکتی انجام دهد (ثبت‌نام، افزودن، ویرایش و غیره) به‌صورت خودکار اینجا ثبت می‌شود."
              : "Every action any user in any company takes (signups, creates, edits, etc.) is logged here automatically."}
          </p>
          {actionsLoading ? (
            <PageSpinner />
          ) : !actionsPage || actionsPage.items.length === 0 ? (
            <p className="text-sm text-muted">{fa ? "هنوز اکشنی ثبت نشده است." : "No actions logged yet."}</p>
          ) : (
            <Card className="overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-start text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 text-start">{fa ? "شرکت / کاربر" : "Company / user"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "اکشن" : "Action"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "منبع" : "Source"}</th>
                    <th className="px-4 py-3 text-start">{fa ? "تاریخ" : "Date"}</th>
                  </tr>
                </thead>
                <tbody>
                  {actionsPage.items.map((a) => (
                    <tr key={a.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3">
                        <div className="font-medium text-ink">{a.organization_name}</div>
                        <div className="text-xs text-muted">{a.user_name ?? "-"}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge>{a.tool_name}</Badge>
                        {a.entity_type && (
                          <span className="ms-1 text-xs text-muted">
                            {a.entity_type}
                            {a.entity_id ? ` #${a.entity_id}` : ""}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">{a.source}</td>
                      <td className="px-4 py-3 text-xs text-muted">{new Date(a.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {replying && <ReplyModal request={replying} onClose={() => setReplying(null)} />}
    </div>
  );
}

export default function PlatformAdmin() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const queryClient = useQueryClient();
  const [editingOrg, setEditingOrg] = useState<PlatformOrganization | null>(null);
  const [mainTab, setMainTab] = useState<"organizations" | "requests">("organizations");
  const [approvingOrgId, setApprovingOrgId] = useState<number | null>(null);

  const { data: orgs, isLoading } = useQuery({
    queryKey: ["platform-admin-orgs"],
    queryFn: platformAdminApi.listOrganizations,
  });

  const approveTrialMutation = useMutation({
    mutationFn: (orgId: number) => platformAdminApi.approveTrial(orgId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-orgs"] });
      toast.success(fa ? "دورهٔ آزمایشی ۱۴ روزه فعال شد" : "14-day trial activated");
    },
    onError: (err) => toast.error(errorMessage(err)),
    onSettled: () => setApprovingOrgId(null),
  });

  const statusMutation = useMutation({
    mutationFn: ({ orgId, isActive }: { orgId: number; isActive: boolean }) => platformAdminApi.setStatus(orgId, isActive),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-orgs"] });
      toast.success(
        vars.isActive
          ? fa
            ? "شرکت فعال شد"
            : "Organization activated"
          : fa
          ? "شرکت غیرفعال شد"
          : "Organization deactivated"
      );
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Building2 className="h-5 w-5 text-primary" />
        <h1 className="font-display text-2xl font-medium text-ink">{fa ? "پنل مدیریت پلتفرم" : "Platform Admin"}</h1>
      </div>
      <p className="text-sm text-muted">
        {fa
          ? "این پنل فقط برای ایمیل ادمین اصلی قابل مشاهده است و به شما اجازه می‌دهد اشتراک، وضعیت فعال/غیرفعال و محدودیت‌های اختصاصی هر شرکت را مدیریت کنید."
          : "Visible only to the platform owner's email. Manage every company's subscription, active/inactive status, and custom limits from here."}
      </p>

      <div className="flex items-center gap-2 border-b border-border">
        <button
          onClick={() => setMainTab("organizations")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            mainTab === "organizations" ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <Building2 className="h-4 w-4" />
          {fa ? "شرکت‌ها" : "Organizations"}
        </button>
        <button
          onClick={() => setMainTab("requests")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            mainTab === "requests" ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <Inbox className="h-4 w-4" />
          {fa ? "درخواست‌ها" : "Requests"}
        </button>
      </div>

      {mainTab === "requests" ? (
        <RequestsTab />
      ) : isLoading ? (
        <PageSpinner />
      ) : (
        <>
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-start text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-3 text-start">{fa ? "شرکت" : "Company"}</th>
              <th className="px-4 py-3 text-start">{fa ? "کاربران" : "Users"}</th>
              <th className="px-4 py-3 text-start">{fa ? "پلن" : "Plan"}</th>
              <th className="px-4 py-3 text-start">{fa ? "وضعیت اشتراک" : "Sub. status"}</th>
              <th className="px-4 py-3 text-start">{fa ? "وضعیت شرکت" : "Org status"}</th>
              <th className="px-4 py-3 text-start">{fa ? "عملیات" : "Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {orgs?.map((org) => (
              <tr key={org.id} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{org.name}</div>
                  <div className="text-xs text-muted">{org.slug}</div>
                </td>
                <td className="px-4 py-3">{org.user_count}</td>
                <td className="px-4 py-3">
                  <Badge>{org.effective_plan}</Badge>
                  {Object.keys(org.limit_overrides).length > 0 && (
                    <span className="ms-1 text-xs text-primary">
                      {fa ? "دارای محدودیت اختصاصی" : "custom limits"}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge
                    value={org.status}
                    label={org.status === "pending_trial" ? (fa ? "در انتظار تأیید" : "Pending approval") : undefined}
                  />
                  {org.is_trial_expired && (
                    <span className="ms-1 text-xs text-danger">{fa ? "دوره آزمایشی تمام شده" : "trial expired"}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {org.is_active ? (
                    <Badge color="#14D9A6">{fa ? "فعال" : "Active"}</Badge>
                  ) : (
                    <Badge color="#F2555B">{fa ? "غیرفعال" : "Inactive"}</Badge>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setEditingOrg(org)}>
                      <Settings2 className="h-4 w-4" />
                      {fa ? "مدیریت" : "Manage"}
                    </Button>
                    {org.status === "pending_trial" && (
                      <Button
                        size="sm"
                        isLoading={approveTrialMutation.isPending && approvingOrgId === org.id}
                        onClick={() => {
                          setApprovingOrgId(org.id);
                          approveTrialMutation.mutate(org.id);
                        }}
                      >
                        <ShieldCheck className="h-4 w-4" />
                        {fa ? "تأیید تریال" : "Approve trial"}
                      </Button>
                    )}
                    {org.is_active ? (
                      <Button
                        variant="danger"
                        size="sm"
                        isLoading={statusMutation.isPending}
                        onClick={() => statusMutation.mutate({ orgId: org.id, isActive: false })}
                      >
                        <ShieldOff className="h-4 w-4" />
                        {fa ? "غیرفعال کردن" : "Deactivate"}
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        isLoading={statusMutation.isPending}
                        onClick={() => statusMutation.mutate({ orgId: org.id, isActive: true })}
                      >
                        <ShieldCheck className="h-4 w-4" />
                        {fa ? "فعال کردن" : "Activate"}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {editingOrg && <OrgEditModal org={editingOrg} onClose={() => setEditingOrg(null)} />}
        </>
      )}
    </div>
  );
}
