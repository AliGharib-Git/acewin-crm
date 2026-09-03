import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Modal, Button, Input, Textarea } from "../ui";
import { companiesApi, type CompanyInput } from "../../api/companies";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { Company } from "../../types";

const emptyForm: CompanyInput = { name: "", industry: "", website: "", phone: "", address: "", notes: "" };

export function CompanyFormModal({
  open,
  onClose,
  company,
}: {
  open: boolean;
  onClose: () => void;
  company?: Company | null;
}) {
  const { t } = useLanguage();
  const [form, setForm] = useState<CompanyInput>(emptyForm);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (company) {
      setForm({
        name: company.name,
        industry: company.industry ?? "",
        website: company.website ?? "",
        phone: company.phone ?? "",
        address: company.address ?? "",
        notes: company.notes ?? "",
      });
    } else {
      setForm(emptyForm);
    }
  }, [company, open]);

  const mutation = useMutation({
    mutationFn: (data: CompanyInput) => (company ? companiesApi.update(company.id, data) : companiesApi.create(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      toast.success(company ? t("companies.updated") : t("companies.created"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error(t("companies.nameRequired"));
      return;
    }
    mutation.mutate({
      ...form,
      industry: form.industry || null,
      website: form.website || null,
      phone: form.phone || null,
      address: form.address || null,
      notes: form.notes || null,
    });
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={company ? t("companies.editCompany") : t("companies.new")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} isLoading={mutation.isPending}>
            {company ? t("common.save") : t("common.create")}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label={t("common.name")} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t("companies.industry")}
            value={form.industry ?? ""}
            onChange={(e) => setForm({ ...form, industry: e.target.value })}
          />
          <Input
            label={t("companies.website")}
            value={form.website ?? ""}
            onChange={(e) => setForm({ ...form, website: e.target.value })}
          />
        </div>
        <Input label={t("common.phone")} value={form.phone ?? ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <Textarea
          label={t("companies.address")}
          value={form.address ?? ""}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
        <Textarea label={t("common.notes")} value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </form>
    </Modal>
  );
}
