import { Mail, Phone, Pencil, Trash2, Flame } from "lucide-react";
import { StatusBadge, Badge } from "../ui";
import { useLanguage } from "../../context/LanguageContext";
import type { ContactListItem } from "../../types";

export function ContactTable({
  contacts,
  onRowClick,
  onEdit,
  onDelete,
}: {
  contacts: ContactListItem[];
  onRowClick: (contact: ContactListItem) => void;
  onEdit: (contact: ContactListItem) => void;
  onDelete: (contact: ContactListItem) => void;
}) {
  const { t } = useLanguage();
  const statusLabel = (status: ContactListItem["status"]) =>
    t(`contacts.status.${status}` as "contacts.status.lead");
  const priorityLabel = (priority: ContactListItem["priority"]) =>
    t(`contacts.priority.${priority}` as "contacts.priority.low");
  const engagementLabel = (label: string) =>
    t(`contacts.engagement.${label}` as "contacts.engagement.low");

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
            <th className="px-4 py-3 font-medium">{t("common.name")}</th>
            <th className="px-4 py-3 font-medium">{t("contacts.company")}</th>
            <th className="px-4 py-3 font-medium">{t("common.email")}</th>
            <th className="px-4 py-3 font-medium">{t("common.status")}</th>
            <th className="px-4 py-3 font-medium">{t("contacts.priority")}</th>
            <th className="px-4 py-3 font-medium">{t("contacts.engagement")}</th>
            <th className="px-4 py-3 font-medium">{t("contacts.tags")}</th>
            <th className="px-4 py-3 font-medium">{t("common.assignedTo")}</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => (
            <tr
              key={c.id}
              onClick={() => onRowClick(c)}
              className="cursor-pointer border-b border-border last:border-0 hover:bg-paper/60"
            >
              <td className="px-4 py-3 font-medium text-ink">
                {c.first_name} {c.last_name}
              </td>
              <td className="px-4 py-3 text-muted">{c.company_name ?? "—"}</td>
              <td className="px-4 py-3 text-muted">
                <div className="flex flex-col gap-0.5">
                  {c.email && (
                    <span className="flex items-center gap-1.5 text-xs">
                      <Mail className="h-3 w-3" /> {c.email}
                    </span>
                  )}
                  {c.phone && (
                    <span className="flex items-center gap-1.5 text-xs">
                      <Phone className="h-3 w-3" /> {c.phone}
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge value={c.status} label={statusLabel(c.status)} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge value={c.priority} label={priorityLabel(c.priority)} />
              </td>
              <td className="px-4 py-3">
                {c.engagement ? (
                  <span className="flex items-center gap-1">
                    {c.engagement.label === "low" && <Flame className="h-3.5 w-3.5 text-danger" />}
                    <StatusBadge
                      value={c.engagement.label === "high" ? "completed" : c.engagement.label === "low" ? "high" : "medium"}
                      label={engagementLabel(c.engagement.label)}
                    />
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.tags.map((tag) => (
                    <Badge key={tag.id} color={tag.color}>
                      {tag.name}
                    </Badge>
                  ))}
                </div>
              </td>
              <td className="px-4 py-3 text-muted">{c.assigned_to?.full_name ?? "—"}</td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(c);
                    }}
                    className="rounded p-1.5 text-muted hover:bg-primary/10 hover:text-primary"
                    aria-label={t("common.edit")}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c);
                    }}
                    className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                    aria-label={t("common.delete")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
