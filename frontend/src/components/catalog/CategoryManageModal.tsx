import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Trash2, Plus } from "lucide-react";
import { Modal, Button, Input } from "../ui";
import { catalogApi } from "../../api/catalog";
import { errorMessage } from "../../api/client";
import { useLanguage } from "../../context/LanguageContext";
import type { CatalogCategory } from "../../types";

const CATEGORY_COLORS = ["#14D9A6", "#22F0C2", "#22D3EE", "#93A6A6", "#F2555B"];

export function CategoryManageModal({
  open,
  onClose,
  categories,
}: {
  open: boolean;
  onClose: () => void;
  categories: CatalogCategory[];
}) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      catalogApi.createCategory({
        name: newName,
        order: categories.length,
        color: CATEGORY_COLORS[categories.length % CATEGORY_COLORS.length],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-categories"] });
      setNewName("");
      toast.success(t("catalog.categoryCreated"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => catalogApi.removeCategory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-categories"] });
      queryClient.invalidateQueries({ queryKey: ["catalog-items"] });
      toast.success(t("catalog.categoryDeleted"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal open={open} onClose={onClose} title={t("catalog.manageCategories")}>
      <div className="space-y-2">
        {categories.map((c) => (
          <div key={c.id} className="flex items-center gap-3 rounded border border-border p-2.5">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: c.color }} />
            <span className="flex-1 text-sm font-medium text-ink">{c.name}</span>
            <span className="text-xs text-muted">{c.item_count}</span>
            <button
              onClick={() => {
                if (window.confirm(t("catalog.confirmDeleteCategory", { name: c.name }))) deleteMutation.mutate(c.id);
              }}
              className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="mt-4 flex gap-2">
        <Input
          placeholder={t("catalog.newCategoryName")}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1"
        />
        <Button variant="secondary" disabled={!newName.trim()} isLoading={createMutation.isPending} onClick={() => createMutation.mutate()}>
          <Plus className="h-4 w-4" /> {t("common.add")}
        </Button>
      </div>
    </Modal>
  );
}
