import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Trash2 } from "lucide-react";
import { Modal, Button, Input, Select } from "../ui";
import { dealsApi, type DealInput, type DealItemInput } from "../../api/deals";
import { pipelineApi } from "../../api/pipeline";
import { contactsApi } from "../../api/contacts";
import { companiesApi } from "../../api/companies";
import { usersApi } from "../../api/users";
import { catalogApi } from "../../api/catalog";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { Deal } from "../../types";

const emptyForm: DealInput = {
  title: "",
  value: 0,
  probability: 50,
  expected_close_date: "",
  stage_id: 0,
  contact_id: null,
  company_id: null,
  assigned_to_id: null,
};

// Local editable line -- a `key` (not the server id, which a new/custom
// line doesn't have yet) so React can key the list stably while typing.
interface LineForm {
  key: string;
  catalog_item_id: number | null;
  name: string;
  unit_price: number;
  quantity: number;
}

let lineKeySeq = 0;
function nextLineKey() {
  lineKeySeq += 1;
  return `line-${lineKeySeq}`;
}

export function DealFormModal({
  open,
  onClose,
  deal,
  defaultStageId,
}: {
  open: boolean;
  onClose: () => void;
  deal?: Deal | null;
  defaultStageId?: number | null;
}) {
  const { t } = useLanguage();
  const [form, setForm] = useState<DealInput>(emptyForm);
  const [lines, setLines] = useState<LineForm[]>([]);
  const [pickedCatalogId, setPickedCatalogId] = useState<string>("");
  const queryClient = useQueryClient();

  const { data: stages } = useQuery({ queryKey: ["pipeline-stages"], queryFn: pipelineApi.list, enabled: open });
  const { data: contactsPage } = useQuery({
    queryKey: ["contacts", "all"],
    queryFn: () => contactsApi.list({ page_size: 100 }),
    enabled: open,
  });
  const { data: companiesPage } = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => companiesApi.list({ page_size: 100 }),
    enabled: open,
  });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: usersApi.list, enabled: open });
  const { data: catalogItems } = useQuery({
    queryKey: ["catalog-items", "picker"],
    queryFn: () => catalogApi.listItems({ include_inactive: false }),
    enabled: open,
  });

  useEffect(() => {
    if (deal) {
      setForm({
        title: deal.title,
        value: deal.value,
        probability: deal.probability,
        expected_close_date: deal.expected_close_date ?? "",
        stage_id: deal.stage_id,
        contact_id: deal.contact_id,
        company_id: deal.company_id,
        assigned_to_id: deal.assigned_to?.id ?? null,
      });
      setLines(
        deal.items.map((li) => ({
          key: nextLineKey(),
          catalog_item_id: li.catalog_item_id,
          name: li.name,
          unit_price: li.unit_price,
          quantity: li.quantity,
        }))
      );
    } else {
      setForm({ ...emptyForm, stage_id: defaultStageId ?? stages?.[0]?.id ?? 0 });
      setLines([]);
    }
    setPickedCatalogId("");
  }, [deal, open, defaultStageId, stages]);

  const mutation = useMutation({
    mutationFn: (data: DealInput) => (deal ? dealsApi.update(deal.id, data) : dealsApi.create(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(deal ? t("deals.updated") : t("deals.created"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const quoteTotal = lines.reduce((sum, l) => sum + l.unit_price * l.quantity, 0);

  function addCatalogLine() {
    if (!pickedCatalogId) return;
    const item = catalogItems?.find((c) => c.id === Number(pickedCatalogId));
    if (!item) return;
    setLines((prev) => [
      ...prev,
      { key: nextLineKey(), catalog_item_id: item.id, name: item.name, unit_price: item.price, quantity: 1 },
    ]);
    setPickedCatalogId("");
  }

  function addCustomLine() {
    setLines((prev) => [...prev, { key: nextLineKey(), catalog_item_id: null, name: "", unit_price: 0, quantity: 1 }]);
  }

  function updateLine(key: string, patch: Partial<LineForm>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }

  function removeLine(key: string) {
    setLines((prev) => prev.filter((l) => l.key !== key));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) {
      toast.error(t("deals.titleRequired"));
      return;
    }
    if (!form.stage_id) {
      toast.error(t("deals.stageRequired"));
      return;
    }
    const items: DealItemInput[] = lines.map((l) => ({
      catalog_item_id: l.catalog_item_id,
      name: l.name,
      unit_price: l.unit_price,
      quantity: l.quantity,
    }));
    mutation.mutate({
      ...form,
      value: lines.length ? quoteTotal : form.value,
      expected_close_date: form.expected_close_date || null,
      items,
    });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={deal ? t("deals.editDeal") : t("deals.new")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} isLoading={mutation.isPending}>
            {deal ? t("common.save") : t("common.create")}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label={t("common.title")}
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t("deals.value")}
            type="number"
            min={0}
            step="0.01"
            disabled={lines.length > 0}
            value={lines.length ? quoteTotal : form.value}
            onChange={(e) => setForm({ ...form, value: Number(e.target.value) })}
            hint={lines.length ? t("deals.items.autoValueHint") : undefined}
          />
          <Input
            label={t("deals.probability")}
            type="number"
            min={0}
            max={100}
            value={form.probability}
            onChange={(e) => setForm({ ...form, probability: Number(e.target.value) })}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={t("deals.stage")}
            required
            value={form.stage_id || ""}
            onChange={(e) => setForm({ ...form, stage_id: Number(e.target.value) })}
          >
            <option value="" disabled>
              {t("deals.chooseStage")}
            </option>
            {stages?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Input
            label={t("deals.expectedClose")}
            type="date"
            value={form.expected_close_date ?? ""}
            onChange={(e) => setForm({ ...form, expected_close_date: e.target.value })}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={t("common.relatedContact")}
            value={form.contact_id ?? ""}
            onChange={(e) => setForm({ ...form, contact_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t("deals.noContact")}</option>
            {contactsPage?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.first_name} {c.last_name}
              </option>
            ))}
          </Select>
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
        </div>
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

        <div className="border-t border-border pt-4">
          <p className="mb-2 text-sm font-medium text-ink">{t("deals.items.title")}</p>

          {lines.length === 0 && <p className="mb-2 text-xs text-muted">{t("deals.items.empty")}</p>}

          {lines.length > 0 && (
            <div className="mb-3 space-y-2">
              {lines.map((line) => (
                <div key={line.key} className="flex items-center gap-2 rounded border border-border p-2">
                  <input
                    className="min-w-0 flex-1 rounded border border-border bg-surface px-2 py-1.5 text-sm text-ink focus:border-primary focus:outline-none"
                    placeholder={t("deals.items.name")}
                    value={line.name}
                    disabled={line.catalog_item_id !== null}
                    onChange={(e) => updateLine(line.key, { name: e.target.value })}
                  />
                  <input
                    className="w-20 shrink-0 rounded border border-border bg-surface px-2 py-1.5 text-sm text-ink focus:border-primary focus:outline-none"
                    type="number"
                    min={1}
                    value={line.quantity}
                    onChange={(e) => updateLine(line.key, { quantity: Math.max(1, Number(e.target.value)) })}
                  />
                  <input
                    className="w-28 shrink-0 rounded border border-border bg-surface px-2 py-1.5 text-sm text-ink focus:border-primary focus:outline-none"
                    type="number"
                    min={0}
                    step="0.01"
                    value={line.unit_price}
                    onChange={(e) => updateLine(line.key, { unit_price: Math.max(0, Number(e.target.value)) })}
                  />
                  <span className="w-24 shrink-0 text-end font-mono text-sm tabular text-ink">
                    {(line.unit_price * line.quantity).toLocaleString()}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeLine(line.key)}
                    aria-label={t("deals.items.remove")}
                    className="shrink-0 rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <div className="flex justify-end pe-9 text-sm font-medium text-ink">
                {t("deals.items.total")}: {quoteTotal.toLocaleString()}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Select value={pickedCatalogId} onChange={(e) => setPickedCatalogId(e.target.value)} className="max-w-xs">
              <option value="">{t("deals.items.chooseCatalogItem")}</option>
              {catalogItems?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.price.toLocaleString()} {c.currency}
                </option>
              ))}
            </Select>
            <Button type="button" variant="secondary" size="sm" disabled={!pickedCatalogId} onClick={addCatalogLine}>
              <Plus className="h-3.5 w-3.5" /> {t("deals.items.add")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={addCustomLine}>
              <Plus className="h-3.5 w-3.5" /> {t("deals.items.addCustom")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
