import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Modal, Button, Input, Select, Textarea } from "../ui";
import { catalogApi, type CatalogItemInput } from "../../api/catalog";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { BillingType, CatalogCategory, CatalogItem } from "../../types";

const emptyForm: CatalogItemInput = {
  name: "",
  description: "",
  sku: "",
  price: 0,
  currency: "USD",
  billing_type: "one_time",
  category_id: null,
  is_active: true,
};

export function CatalogItemFormModal({
  open,
  onClose,
  item,
  categories,
  defaultCategoryId,
}: {
  open: boolean;
  onClose: () => void;
  item?: CatalogItem | null;
  categories: CatalogCategory[];
  defaultCategoryId?: number | null;
}) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CatalogItemInput>(emptyForm);

  useEffect(() => {
    if (item) {
      setForm({
        name: item.name,
        description: item.description ?? "",
        sku: item.sku ?? "",
        price: item.price,
        currency: item.currency,
        billing_type: item.billing_type,
        category_id: item.category_id,
        is_active: item.is_active,
      });
    } else {
      setForm({ ...emptyForm, category_id: defaultCategoryId ?? null });
    }
  }, [item, open, defaultCategoryId]);

  const mutation = useMutation({
    mutationFn: (data: CatalogItemInput) => (item ? catalogApi.updateItem(item.id, data) : catalogApi.createItem(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-items"] });
      queryClient.invalidateQueries({ queryKey: ["catalog-categories"] });
      toast.success(item ? t("catalog.itemUpdated") : t("catalog.itemCreated"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name?.trim()) {
      toast.error(t("common.titleRequired"));
      return;
    }
    mutation.mutate({ ...form, sku: form.sku || null, description: form.description || null });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={item ? t("catalog.editItem") : t("catalog.newItem")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} isLoading={mutation.isPending}>
            {item ? t("common.save") : t("common.create")}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label={t("catalog.itemName")}
          required
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <Textarea
          label={t("catalog.description")}
          value={form.description ?? ""}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t("catalog.price")}
            type="number"
            min={0}
            step="0.01"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
          />
          <Input
            label={t("catalog.currency")}
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={t("catalog.billingType")}
            value={form.billing_type}
            onChange={(e) => setForm({ ...form, billing_type: e.target.value as BillingType })}
          >
            <option value="one_time">{t("catalog.billing.one_time")}</option>
            <option value="monthly">{t("catalog.billing.monthly")}</option>
            <option value="yearly">{t("catalog.billing.yearly")}</option>
          </Select>
          <Select
            label={t("catalog.category")}
            value={form.category_id ?? ""}
            onChange={(e) => setForm({ ...form, category_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">{t("catalog.uncategorized")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
        <Input label={t("catalog.sku")} value={form.sku ?? ""} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          {t("catalog.active")}
        </label>
      </form>
    </Modal>
  );
}
