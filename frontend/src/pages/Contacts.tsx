import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Search, ChevronLeft, ChevronRight, Users } from "lucide-react";
import { Card, Button, Select, EmptyState, PageSpinner } from "../components/ui";
import { ContactTable } from "../components/contacts/ContactTable";
import { ContactFormModal } from "../components/contacts/ContactFormModal";
import { contactsApi } from "../api/contacts";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { ContactListItem, ContactPriority, ContactStatus } from "../types";

const PAGE_SIZE = 15;

export default function Contacts() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ContactStatus | "">("");
  const [priority, setPriority] = useState<ContactPriority | "">("");
  const [sortByPriority, setSortByPriority] = useState(false);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["contacts", { search, status, priority, sortByPriority, page }],
    queryFn: () =>
      contactsApi.list({
        search: search || undefined,
        status: status || undefined,
        priority: priority || undefined,
        sort: sortByPriority ? "priority" : undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => contactsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success(t("contacts.deleted"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleDelete(contact: ContactListItem) {
    if (window.confirm(t("contacts.confirmDelete", { name: `${contact.first_name} ${contact.last_name}` }))) {
      deleteMutation.mutate(contact.id);
    }
  }

  function openCreate() {
    setEditingId(null);
    setModalOpen(true);
  }

  function openEdit(contact: ContactListItem) {
    setEditingId(contact.id);
    setModalOpen(true);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{t("contacts.title")}</h1>
          <p className="mt-1 text-sm text-muted">{data ? t("common.total", { count: data.total }) : t("common.loading")}</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> {t("contacts.new")}
        </Button>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              className="w-full rounded border border-border bg-surface py-2 ps-9 pe-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder={t("contacts.searchPlaceholder")}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as ContactStatus | "");
              setPage(1);
            }}
            className="w-40"
          >
            <option value="">{t("common.allStatuses")}</option>
            <option value="lead">{t("contacts.status.lead")}</option>
            <option value="prospect">{t("contacts.status.prospect")}</option>
            <option value="customer">{t("contacts.status.customer")}</option>
            <option value="inactive">{t("contacts.status.inactive")}</option>
          </Select>
          <Select
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value as ContactPriority | "");
              setPage(1);
            }}
            className="w-40"
          >
            <option value="">{t("contacts.priority")}</option>
            <option value="high">{t("contacts.priority.high")}</option>
            <option value="medium">{t("contacts.priority.medium")}</option>
            <option value="low">{t("contacts.priority.low")}</option>
          </Select>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={sortByPriority}
              onChange={(e) => {
                setSortByPriority(e.target.checked);
                setPage(1);
              }}
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
            />
            {t("contacts.sortByPriority")}
          </label>
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <PageSpinner />
        ) : data && data.items.length > 0 ? (
          <>
            <ContactTable
              contacts={data.items}
              onRowClick={(c) => navigate(`/contacts/${c.id}`)}
              onEdit={openEdit}
              onDelete={handleDelete}
            />
            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <span className="text-xs text-muted">
                {t("common.pageOf", { page, total: totalPages })}
              </span>
              <div className="flex gap-1">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded p-1.5 text-muted hover:bg-paper disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded p-1.5 text-muted hover:bg-paper disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            icon={<Users className="h-8 w-8" />}
            title={t("contacts.emptyTitle")}
            description={t("contacts.emptyDescription")}
            action={
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" /> {t("contacts.new")}
              </Button>
            }
          />
        )}
      </Card>

      <ContactFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditingId(null);
        }}
        contactId={editingId}
      />
    </div>
  );
}
