import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Modal, Button, Input, Select, Textarea, PageSpinner } from "../ui";
import { contactsApi, type ContactInput } from "../../api/contacts";
import { companiesApi } from "../../api/companies";
import { usersApi } from "../../api/users";
import { tagsApi } from "../../api/tags";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { ContactPriority, ContactStatus } from "../../types";

const STATUS_OPTIONS: ContactStatus[] = ["lead", "prospect", "customer", "inactive"];
const PRIORITY_OPTIONS: ContactPriority[] = ["high", "medium", "low"];

const emptyForm: ContactInput = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  job_title: "",
  status: "lead",
  priority: "medium",
  source: "",
  notes: "",
  company_id: null,
  assigned_to_id: null,
  tag_ids: [],
};

export function ContactFormModal({
  open,
  onClose,
  contactId,
}: {
  open: boolean;
  onClose: () => void;
  contactId?: number | null;
}) {
  const { t } = useLanguage();
  const [form, setForm] = useState<ContactInput>(emptyForm);
  const queryClient = useQueryClient();
  const isEditing = Boolean(contactId);

  const { data: contact, isLoading: loadingContact } = useQuery({
    queryKey: ["contact", contactId],
    queryFn: () => contactsApi.get(contactId as number),
    enabled: open && isEditing,
  });

  const { data: companiesPage } = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => companiesApi.list({ page_size: 100 }),
    enabled: open,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: usersApi.list, enabled: open });
  const { data: tags } = useQuery({ queryKey: ["tags"], queryFn: tagsApi.list, enabled: open });

  useEffect(() => {
    if (contact) {
      setForm({
        first_name: contact.first_name,
        last_name: contact.last_name,
        email: contact.email ?? "",
        phone: contact.phone ?? "",
        job_title: contact.job_title ?? "",
        status: contact.status,
        priority: contact.priority,
        source: contact.source ?? "",
        notes: contact.notes ?? "",
        company_id: contact.company_id,
        assigned_to_id: contact.assigned_to?.id ?? null,
        tag_ids: contact.tags.map((t) => t.id),
      });
    } else if (!isEditing) {
      setForm(emptyForm);
    }
  }, [contact, isEditing, open]);

  const mutation = useMutation({
    mutationFn: (data: ContactInput) =>
      isEditing ? contactsApi.update(contactId as number, data) : contactsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      if (isEditing) queryClient.invalidateQueries({ queryKey: ["contact", contactId] });
      toast.success(isEditing ? t("contacts.updated") : t("contacts.created"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.first_name.trim()) {
      toast.error(t("contacts.firstNameRequired"));
      return;
    }
    mutation.mutate({
      ...form,
      email: form.email || null,
      phone: form.phone || null,
      job_title: form.job_title || null,
      source: form.source || null,
      notes: form.notes || null,
    });
  }

  function toggleTag(id: number) {
    setForm((f) => ({
      ...f,
      tag_ids: f.tag_ids?.includes(id) ? f.tag_ids.filter((t) => t !== id) : [...(f.tag_ids ?? []), id],
    }));
  }

  const showLoading = isEditing && loadingContact;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEditing ? t("contacts.editContact") : t("contacts.new")}
      footer={
        !showLoading && (
          <>
            <Button variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSubmit} isLoading={mutation.isPending}>
              {isEditing ? t("common.save") : t("common.create")}
            </Button>
          </>
        )
      }
    >
      {showLoading ? (
        <PageSpinner />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t("contacts.firstName")}
              required
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
            <Input
              label={t("contacts.lastName")}
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t("common.email")}
              type="email"
              value={form.email ?? ""}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <Input
              label={t("common.phone")}
              value={form.phone ?? ""}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t("contacts.jobTitle")}
              value={form.job_title ?? ""}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
            />
            <Select
              label={t("common.status")}
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as ContactStatus })}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {t(`contacts.status.${s}` as "contacts.status.lead")}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select
              label={t("contacts.priority")}
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value as ContactPriority })}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {t(`contacts.priority.${p}` as "contacts.priority.low")}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select
              label={t("contacts.company")}
              value={form.company_id ?? ""}
              onChange={(e) => setForm({ ...form, company_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("deals.noCompany")}</option>
              {companiesPage?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <Select
              label={t("common.assignedTo")}
              value={form.assigned_to_id ?? ""}
              onChange={(e) => setForm({ ...form, assigned_to_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("common.unassigned")}</option>
              {users?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name}
                </option>
              ))}
            </Select>
          </div>
          <Input
            label={t("contacts.source")}
            placeholder={t("contacts.sourcePlaceholder")}
            value={form.source ?? ""}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
          />
          {tags && tags.length > 0 && (
            <div>
              <span className="mb-1.5 block text-sm font-medium text-ink">{t("contacts.tags")}</span>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => {
                  const active = form.tag_ids?.includes(tag.id);
                  return (
                    <button
                      type="button"
                      key={tag.id}
                      onClick={() => toggleTag(tag.id)}
                      className="rounded-full px-2.5 py-1 text-xs font-medium transition-colors"
                      style={
                        active
                          ? { backgroundColor: tag.color, color: "white" }
                          : { backgroundColor: `${tag.color}1A`, color: tag.color }
                      }
                    >
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <Textarea
            label={t("common.notes")}
            value={form.notes ?? ""}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </form>
      )}
    </Modal>
  );
}
