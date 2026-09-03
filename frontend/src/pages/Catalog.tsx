import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Pencil, Trash2, Package, Settings2, Search, X, Boxes, CheckCircle2, Tags, Coins } from "lucide-react";
import { Button, Card, Badge, PageSpinner, EmptyState, Select } from "../components/ui";
import { CatalogItemFormModal } from "../components/catalog/CatalogItemFormModal";
import { CategoryManageModal } from "../components/catalog/CategoryManageModal";
import { catalogApi } from "../api/catalog";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import type { CatalogItem } from "../types";

const CATEGORY_FALLBACK_COLOR = "#93A6A6";
const BILLING_COLORS: Record<string, string> = {
  one_time: "#93A6A6",
  monthly: "#22D3EE",
  yearly: "#14D9A6",
};

export default function Catalog() {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();

  const [activeCategory, setActiveCategory] = useState<number | "all">("all");
  const [showInactive, setShowInactive] = useState(false);
  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CatalogItem | null>(null);
  const [categoryModalOpen, setCategoryModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "price_asc" | "price_desc" | "newest">("name");

  const { data: categories, isLoading: loadingCategories } = useQuery({
    queryKey: ["catalog-categories"],
    queryFn: catalogApi.listCategories,
  });
  const { data: items, isLoading: loadingItems } = useQuery({
    queryKey: ["catalog-items", showInactive],
    queryFn: () => catalogApi.listItems({ include_inactive: showInactive }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => catalogApi.removeItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["catalog-items"] });
      queryClient.invalidateQueries({ queryKey: ["catalog-categories"] });
      toast.success(t("catalog.itemDeleted"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const currencyFormatters = useMemo(() => new Map<string, Intl.NumberFormat>(), []);
  function formatPrice(price: number, currency: string) {
    let fmt = currencyFormatters.get(currency);
    if (!fmt) {
      try {
        fmt = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
          style: "currency",
          currency,
          maximumFractionDigits: 0,
        });
      } catch {
        fmt = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", { maximumFractionDigits: 0 });
      }
      currencyFormatters.set(currency, fmt);
    }
    return fmt.format(price);
  }

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    const result = (items ?? []).filter((item) => {
      if (activeCategory !== "all" && item.category_id !== activeCategory) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.sku ?? "").toLowerCase().includes(q) ||
        (item.description ?? "").toLowerCase().includes(q)
      );
    });
    const sorted = [...result];
    switch (sortBy) {
      case "price_asc":
        sorted.sort((a, b) => a.price - b.price);
        break;
      case "price_desc":
        sorted.sort((a, b) => b.price - a.price);
        break;
      case "newest":
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        break;
      default:
        sorted.sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  }, [items, activeCategory, search, sortBy]);

  // Quick org-wide numbers so an admin can gauge the catalog's shape at a
  // glance -- always computed off the *unfiltered* item list, since these
  // describe the whole catalog, not just what search/category narrowed to.
  const stats = useMemo(() => {
    const all = items ?? [];
    const activeItems = all.filter((i) => i.is_active);
    const valueByCurrency = new Map<string, number>();
    for (const item of activeItems) {
      valueByCurrency.set(item.currency, (valueByCurrency.get(item.currency) ?? 0) + item.price);
    }
    return {
      total: all.length,
      active: activeItems.length,
      categories: categories?.length ?? 0,
      valueByCurrency,
    };
  }, [items, categories]);

  const hasFilters = search.trim().length > 0 || activeCategory !== "all";

  if (loadingCategories || loadingItems) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">{t("catalog.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("catalog.subtitle")}</p>
        </div>
        {isAdmin ? (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setCategoryModalOpen(true)}>
              <Settings2 className="h-4 w-4" /> {t("catalog.manageCategories")}
            </Button>
            <Button
              onClick={() => {
                setEditingItem(null);
                setItemModalOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> {t("catalog.newItem")}
            </Button>
          </div>
        ) : null}
      </div>

      {items && items.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="flex items-center gap-3 p-3.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary">
              <Boxes className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="font-mono text-lg font-medium tabular text-ink">{stats.total}</p>
              <p className="truncate text-xs text-muted">{t("catalog.stats.items")}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 p-3.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#14D9A61A] text-[#14D9A6]">
              <CheckCircle2 className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="font-mono text-lg font-medium tabular text-ink">{stats.active}</p>
              <p className="truncate text-xs text-muted">{t("catalog.stats.active")}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 p-3.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#22D3EE1A] text-[#22D3EE]">
              <Tags className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="font-mono text-lg font-medium tabular text-ink">{stats.categories}</p>
              <p className="truncate text-xs text-muted">{t("catalog.stats.categories")}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3 p-3.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#22F0C21A] text-[#22F0C2]">
              <Coins className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-mono text-sm font-medium tabular text-ink">
                {stats.valueByCurrency.size === 0
                  ? formatPrice(0, "USD")
                  : Array.from(stats.valueByCurrency.entries())
                      .map(([currency, value]) => formatPrice(value, currency))
                      .join(" · ")}
              </p>
              <p className="truncate text-xs text-muted">{t("catalog.stats.value")}</p>
            </div>
          </Card>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("catalog.searchPlaceholder")}
            className="w-full rounded border border-border bg-surface py-1.5 ps-9 pe-8 text-sm text-ink placeholder:text-muted/70 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute end-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
              aria-label={t("catalog.clearFilters")}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <Select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="!w-auto min-w-[9rem]">
          <option value="name">{t("catalog.sort.name")}</option>
          <option value="price_asc">{t("catalog.sort.priceAsc")}</option>
          <option value="price_desc">{t("catalog.sort.priceDesc")}</option>
          <option value="newest">{t("catalog.sort.newest")}</option>
        </Select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActiveCategory("all")}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
            activeCategory === "all" ? "bg-primary text-black" : "bg-surface text-ink border border-border hover:bg-paper"
          }`}
        >
          {t("catalog.allCategories")}
        </button>
        {categories?.map((c) => (
          <button
            key={c.id}
            onClick={() => setActiveCategory(c.id)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              activeCategory === c.id ? "text-white" : "bg-surface text-ink border border-border hover:bg-paper"
            }`}
            style={activeCategory === c.id ? { backgroundColor: c.color } : undefined}
          >
            {c.name} <span className="opacity-70">· {c.item_count}</span>
          </button>
        ))}
        <label className="ms-auto flex items-center gap-1.5 text-xs text-muted">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          {t("catalog.showInactive")}
        </label>
      </div>

      {items && items.length > 0 && (
        <p className="text-xs text-muted">{t("catalog.resultsCount", { count: filteredItems.length, total: items.length })}</p>
      )}

      {!filteredItems.length ? (
        <EmptyState
          icon={<Package className="h-8 w-8" />}
          title={hasFilters ? t("catalog.noResultsTitle") : t("catalog.emptyTitle")}
          description={
            hasFilters ? t("catalog.noResultsDescription") : isAdmin ? t("catalog.emptyDescription") : t("catalog.adminOnlyHint")
          }
          action={
            hasFilters ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch("");
                  setActiveCategory("all");
                }}
              >
                {t("catalog.clearFilters")}
              </Button>
            ) : isAdmin ? (
              <Button
                onClick={() => {
                  setEditingItem(null);
                  setItemModalOpen(true);
                }}
              >
                <Plus className="h-4 w-4" /> {t("catalog.newItem")}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredItems.map((item) => {
            const category = categories?.find((c) => c.id === item.category_id);
            return (
              <Card key={item.id} className={`flex flex-col p-4 ${!item.is_active ? "opacity-60" : ""}`}>
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-display text-base font-medium text-ink">{item.name}</h3>
                  {isAdmin && (
                    <div className="flex shrink-0 gap-1">
                      <button
                        onClick={() => {
                          setEditingItem(item);
                          setItemModalOpen(true);
                        }}
                        className="rounded p-1.5 text-muted hover:bg-white/5 hover:text-ink"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm(t("catalog.confirmDeleteItem", { name: item.name }))) deleteMutation.mutate(item.id);
                        }}
                        className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
                {item.description && <p className="mt-1.5 text-sm text-muted line-clamp-3">{item.description}</p>}
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <Badge color={category?.color ?? CATEGORY_FALLBACK_COLOR}>{category?.name ?? t("catalog.uncategorized")}</Badge>
                  <Badge color={BILLING_COLORS[item.billing_type] ?? CATEGORY_FALLBACK_COLOR}>
                    {t(`catalog.billing.${item.billing_type}` as "catalog.billing.one_time")}
                  </Badge>
                  {!item.is_active && <Badge color="#F2555B">{t("catalog.inactive")}</Badge>}
                </div>
                <div className="mt-auto flex items-end justify-between gap-2 pt-4">
                  {item.sku && <span className="min-w-0 truncate font-mono text-xs text-muted">{item.sku}</span>}
                  <span className="ms-auto shrink-0 font-mono text-lg font-medium tabular text-ink">
                    {formatPrice(item.price, item.currency)}
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <CatalogItemFormModal
        open={itemModalOpen}
        onClose={() => {
          setItemModalOpen(false);
          setEditingItem(null);
        }}
        item={editingItem}
        categories={categories ?? []}
        defaultCategoryId={activeCategory === "all" ? null : activeCategory}
      />
      <CategoryManageModal open={categoryModalOpen} onClose={() => setCategoryModalOpen(false)} categories={categories ?? []} />
    </div>
  );
}
