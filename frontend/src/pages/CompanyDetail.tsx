import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { ArrowLeft, Globe, Phone, MapPin, Pencil, Trash2 } from "lucide-react";
import { Card, Button, StatusBadge, PageSpinner } from "../components/ui";
import { CompanyFormModal } from "../components/companies/CompanyFormModal";
import { companiesApi } from "../api/companies";
import { contactsApi } from "../api/contacts";
import { dealsApi } from "../api/deals";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";

export default function CompanyDetail() {
  const { t, language } = useLanguage();
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);
  const { id } = useParams();
  const companyId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editModalOpen, setEditModalOpen] = useState(false);

  const { data: company, isLoading } = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => companiesApi.get(companyId),
  });
  const { data: contactsPage } = useQuery({
    queryKey: ["contacts", "company", companyId],
    queryFn: () => contactsApi.list({ company_id: companyId, page_size: 50 }),
  });
  const { data: dealsPage } = useQuery({
    queryKey: ["deals", "company", companyId],
    queryFn: () => dealsApi.list({ company_id: companyId, page_size: 50 }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => companiesApi.remove(companyId),
    onSuccess: () => {
      toast.success(t("companies.deleted"));
      navigate("/companies");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading || !company) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <Link to="/companies" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4 rtl:rotate-180" /> {t("companies.backToCompanies")}
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{company.name}</h1>
          {company.industry && <p className="mt-1 text-sm text-muted">{company.industry}</p>}
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditModalOpen(true)}>
            <Pencil className="h-4 w-4" /> {t("common.edit")}
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (window.confirm(t("companies.confirmDeleteCompany"))) deleteMutation.mutate();
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">{t("companies.contactCount")}</span>
          <p className="mt-1 font-mono text-xl font-semibold tabular text-ink">{company.contact_count}</p>
        </Card>
        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">{t("companies.openPipelineValue")}</span>
          <p className="mt-1 font-mono text-xl font-semibold tabular text-ink">
            {formatCurrency(company.open_deal_value)}
          </p>
        </Card>
        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">{t("nav.pipeline")}</span>
          <p className="mt-1 font-mono text-xl font-semibold tabular text-ink">{dealsPage?.total ?? 0}</p>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-1">
          <h3 className="font-display text-sm font-medium text-ink">{t("contacts.details")}</h3>
          <div className="mt-3 space-y-2.5 text-sm">
            {company.website && (
              <div className="flex items-center gap-2 text-ink">
                <Globe className="h-4 w-4 text-muted" /> {company.website}
              </div>
            )}
            {company.phone && (
              <div className="flex items-center gap-2 text-ink">
                <Phone className="h-4 w-4 text-muted" /> {company.phone}
              </div>
            )}
            {company.address && (
              <div className="flex items-center gap-2 text-ink">
                <MapPin className="h-4 w-4 text-muted" /> {company.address}
              </div>
            )}
          </div>
          {company.notes && (
            <div className="mt-3 border-t border-border pt-3 text-sm text-ink whitespace-pre-wrap">{company.notes}</div>
          )}
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("nav.contacts")}</h3>
            <div className="mt-3 space-y-2">
              {!contactsPage?.items.length && <p className="text-sm text-muted">{t("companies.noContactsLinked")}</p>}
              {contactsPage?.items.map((c) => (
                <div
                  key={c.id}
                  onClick={() => navigate(`/contacts/${c.id}`)}
                  className="flex cursor-pointer items-center justify-between rounded border border-border p-2.5 hover:bg-paper/60"
                >
                  <span className="text-sm font-medium text-ink">
                    {c.first_name} {c.last_name}
                  </span>
                  <StatusBadge value={c.status} label={t(`contacts.status.${c.status}` as "contacts.status.lead")} />
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="font-display text-sm font-medium text-ink">{t("deals.title")}</h3>
            <div className="mt-3 space-y-2">
              {!dealsPage?.items.length && <p className="text-sm text-muted">{t("companies.noDealsLinked")}</p>}
              {dealsPage?.items.map((deal) => (
                <div key={deal.id} className="flex items-center justify-between rounded border border-border p-2.5">
                  <div>
                    <p className="text-sm font-medium text-ink">{deal.title}</p>
                    <p className="text-xs text-muted">{deal.stage_name}</p>
                  </div>
                  <span className="font-mono text-sm tabular text-ink">{formatCurrency(deal.value)}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <CompanyFormModal open={editModalOpen} onClose={() => setEditModalOpen(false)} company={company} />
    </div>
  );
}
