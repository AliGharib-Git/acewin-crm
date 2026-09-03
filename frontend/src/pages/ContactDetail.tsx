import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { ArrowLeft, Mail, Phone, Building2, Tag as TagIcon, Pencil, Trash2, Send, PhoneCall } from "lucide-react";
import { Card, Button, StatusBadge, Badge, PageSpinner, Textarea, EmptyState } from "../components/ui";
import { ContactFormModal } from "../components/contacts/ContactFormModal";
import { TaskFormModal } from "../components/tasks/TaskFormModal";
import { contactsApi } from "../api/contacts";
import { activitiesApi } from "../api/activities";
import { dealsApi } from "../api/deals";
import { tasksApi } from "../api/tasks";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";

function useFormatCurrency() {
  const { language } = useLanguage();
  const formatter = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  return (value: number) => formatter.format(value);
}

function useTimeAgo() {
  const { t, language } = useLanguage();
  return (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return t("common.today");
    if (days === 1) return t("common.yesterday");
    if (days < 30) return t("common.daysAgo", { days });
    return new Date(dateStr).toLocaleDateString(language === "fa" ? "fa-IR" : undefined);
  };
}

export default function ContactDetail() {
  const { t } = useLanguage();
  const formatCurrency = useFormatCurrency();
  const timeAgo = useTimeAgo();
  const { id } = useParams();
  const contactId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [callModalOpen, setCallModalOpen] = useState(false);
  const [note, setNote] = useState("");

  const { data: contact, isLoading } = useQuery({
    queryKey: ["contact", contactId],
    queryFn: () => contactsApi.get(contactId),
  });
  const { data: activities } = useQuery({
    queryKey: ["activities", "contact", contactId],
    queryFn: () => activitiesApi.list({ contact_id: contactId }),
  });
  const { data: dealsPage } = useQuery({
    queryKey: ["deals", "contact", contactId],
    queryFn: () => dealsApi.list({ contact_id: contactId, page_size: 50 }),
  });
  const { data: tasksPage } = useQuery({
    queryKey: ["tasks", "contact", contactId],
    queryFn: () => tasksApi.list({ contact_id: contactId, page_size: 50 }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => contactsApi.remove(contactId),
    onSuccess: () => {
      toast.success(t("contacts.deleted"));
      navigate("/contacts");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const noteMutation = useMutation({
    mutationFn: () => activitiesApi.create({ type: "note", content: note, contact_id: contactId }),
    onSuccess: () => {
      setNote("");
      queryClient.invalidateQueries({ queryKey: ["activities", "contact", contactId] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading || !contact) return <PageSpinner />;

  const statusLabel = t(`contacts.status.${contact.status}` as "contacts.status.lead");
  const priorityLabel = t(`contacts.priority.${contact.priority}` as "contacts.priority.low");
  const engagement = contact.engagement;
  const engagementLabel = engagement
    ? t(`contacts.engagement.${engagement.label}` as "contacts.engagement.low")
    : null;
  const lastActivityText = engagement
    ? engagement.days_since_last_activity === null
      ? t("contacts.engagement.noActivity")
      : engagement.days_since_last_activity === 0
      ? t("contacts.engagement.today")
      : t("contacts.engagement.daysAgo", { days: engagement.days_since_last_activity })
    : null;

  return (
    <div className="space-y-6">
      <Link to="/contacts" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" /> {t("contacts.backToContacts")}
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">
            {contact.first_name} {contact.last_name}
          </h1>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge value={contact.status} label={statusLabel} />
            <StatusBadge value={contact.priority} label={priorityLabel} />
            {contact.job_title && <span className="text-sm text-muted">{contact.job_title}</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setCallModalOpen(true)}>
            <PhoneCall className="h-4 w-4" /> {t("contacts.scheduleCall")}
          </Button>
          <Button variant="secondary" onClick={() => setEditModalOpen(true)}>
            <Pencil className="h-4 w-4" /> {t("common.edit")}
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (window.confirm(t("contacts.confirmDeleteContact"))) deleteMutation.mutate();
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("contacts.details")}</h3>
            <div className="mt-3 space-y-2.5 text-sm">
              {contact.email && (
                <div className="flex items-center gap-2 text-ink">
                  <Mail className="h-4 w-4 text-muted" /> {contact.email}
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center gap-2 text-ink">
                  <Phone className="h-4 w-4 text-muted" /> {contact.phone}
                </div>
              )}
              {contact.company_name && (
                <div className="flex items-center gap-2 text-ink">
                  <Building2 className="h-4 w-4 text-muted" /> {contact.company_name}
                </div>
              )}
              {contact.source && (
                <div className="flex items-center gap-2 text-ink">
                  <TagIcon className="h-4 w-4 text-muted" /> {t("contacts.sourcedVia", { source: contact.source })}
                </div>
              )}
            </div>
            {contact.tags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {contact.tags.map((tag) => (
                  <Badge key={tag.id} color={tag.color}>
                    {tag.name}
                  </Badge>
                ))}
              </div>
            )}
            <div className="mt-3 border-t border-border pt-3 text-xs text-muted">
              {t("contacts.owner")}: {contact.assigned_to?.full_name ?? t("common.unassigned")}
            </div>
            {contact.notes && (
              <div className="mt-3 border-t border-border pt-3 text-sm text-ink whitespace-pre-wrap">{contact.notes}</div>
            )}
          </Card>

          {engagement && (
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-sm font-medium text-ink">{t("contacts.engagement")}</h3>
                <StatusBadge
                  value={engagement.label === "high" ? "completed" : engagement.label === "low" ? "high" : "medium"}
                  label={engagementLabel ?? undefined}
                />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="text-muted">{t("contacts.timeline")}</div>
                <div className="text-end text-ink">{lastActivityText}</div>
                <div className="text-muted">{t("contacts.activityTimeline")}</div>
                <div className="text-end text-ink">{engagement.total_activities}</div>
                <div className="text-muted">{t("deals.title")}</div>
                <div className="text-end text-ink">
                  {engagement.open_deal_count > 0 ? formatCurrency(engagement.open_deal_value) : "—"}
                </div>
              </div>
            </Card>
          )}

          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("deals.title")}</h3>
            <div className="mt-3 space-y-2">
              {!dealsPage?.items.length && <p className="text-sm text-muted">{t("contacts.noDealsLinked")}</p>}
              {dealsPage?.items.map((deal) => (
                <div key={deal.id} className="rounded border border-border p-2.5">
                  <p className="text-sm font-medium text-ink">{deal.title}</p>
                  <div className="mt-1 flex items-center justify-between text-xs text-muted">
                    <span>{deal.stage_name}</span>
                    <span className="font-mono tabular">{formatCurrency(deal.value)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("nav.tasks")}</h3>
            <div className="mt-3 space-y-2">
              {!tasksPage?.items.length && <p className="text-sm text-muted">{t("contacts.noTasksLinked")}</p>}
              {tasksPage?.items.map((task) => (
                <div key={task.id} className="flex items-center justify-between rounded border border-border p-2.5">
                  <span className="flex items-center gap-1.5 text-sm text-ink">
                    {task.task_type === "call" && <PhoneCall className="h-3.5 w-3.5 text-accent" />}
                    {task.title}
                  </span>
                  <StatusBadge
                    value={task.status}
                    label={task.status === "completed" ? t("tasks.filterCompleted") : t("tasks.filterPending")}
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("contacts.activityTimeline")}</h3>
            <div className="mt-3 flex gap-2">
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t("contacts.notePlaceholder")}
                className="flex-1"
              />
            </div>
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                disabled={!note.trim()}
                isLoading={noteMutation.isPending}
                onClick={() => noteMutation.mutate()}
              >
                <Send className="h-3.5 w-3.5" /> {t("contacts.addNote")}
              </Button>
            </div>

            <div className="mt-4 space-y-4 border-t border-border pt-4">
              {!activities?.length && (
                <EmptyState title={t("contacts.noActivityTitle")} description={t("contacts.noActivityDesc")} />
              )}
              {activities?.map((activity) => (
                <div key={activity.id} className="flex gap-3">
                  <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                  <div className="flex-1 border-b border-border pb-4 last:border-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium uppercase tracking-wide text-muted">{activity.type}</span>
                      <span className="text-xs text-muted">{timeAgo(activity.created_at)}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink">{activity.content}</p>
                    {activity.created_by && (
                      <p className="mt-1 text-xs text-muted">{t("contacts.by", { name: activity.created_by.full_name })}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <ContactFormModal open={editModalOpen} onClose={() => setEditModalOpen(false)} contactId={contactId} />
      <TaskFormModal
        open={callModalOpen}
        onClose={() => setCallModalOpen(false)}
        defaultTaskType="call"
        defaultContactId={contactId}
      />
    </div>
  );
}
