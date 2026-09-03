import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Search, ChevronLeft, ChevronRight, Building2, Pencil, Trash2 } from "lucide-react";
import { Card, Button, EmptyState, PageSpinner } from "../components/ui";
import { CompanyFormModal } from "../components/companies/CompanyFormModal";
import { companiesApi } from "../api/companies";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import type { Company } from "../types";

const PAGE_SIZE = 15;

export default function Companies() {
  const { t, language } = useLanguage();
  const currencyFormatter = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["companies", { search, page }],
    queryFn: () => companiesApi.list({ search: search || undefined, page, page_size: PAGE_SIZE }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      toast.success(t("companies.deleted"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleDelete(company: Company) {
    if (window.confirm(t("companies.confirmDelete", { name: company.name }))) {
      deleteMutation.mutate(company.id);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{t("companies.title")}</h1>
          <p className="mt-1 text-sm text-muted">{data ? t("common.total", { count: data.total }) : t("common.loading")}</p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setModalOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> {t("companies.new")}
        </Button>
      </div>

      <Card className="p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            className="w-full max-w-sm rounded border border-border bg-surface py-2 ps-9 pe-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder={t("companies.searchPlaceholder")}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <PageSpinner />
        ) : data && data.items.length > 0 ? (
          <>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">{t("common.name")}</th>
                  <th className="px-4 py-3 font-medium">{t("companies.industry")}</th>
                  <th className="px-4 py-3 font-medium">{t("companies.contactCount")}</th>
                  <th className="px-4 py-3 font-medium">{t("companies.openPipelineValue")}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((company) => (
                  <tr
                    key={company.id}
                    onClick={() => navigate(`/companies/${company.id}`)}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-paper/60"
                  >
                    <td className="px-4 py-3 font-medium text-ink">{company.name}</td>
                    <td className="px-4 py-3 text-muted">{company.industry ?? "—"}</td>
                    <td className="px-4 py-3 font-mono tabular text-ink">{company.contact_count}</td>
                    <td className="px-4 py-3 font-mono tabular text-ink">
                      {currencyFormatter.format(company.open_deal_value)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditing(company);
                            setModalOpen(true);
                          }}
                          className="rounded p-1.5 text-muted hover:bg-primary/10 hover:text-primary"
                          aria-label={t("common.edit")}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(company);
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
            icon={<Building2 className="h-8 w-8" />}
            title={t("companies.emptyTitle")}
            description={t("companies.emptyDescription")}
            action={
              <Button onClick={() => setModalOpen(true)}>
                <Plus className="h-4 w-4" /> {t("companies.new")}
              </Button>
            }
          />
        )}
      </Card>

      <CompanyFormModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        company={editing}
      />
    </div>
  );
}
