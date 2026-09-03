import { client } from "./client";
import type { BillingType, CatalogCategory, CatalogItem } from "../types";

export interface CatalogCategoryInput {
  name: string;
  order?: number;
  color?: string;
}

export interface CatalogItemInput {
  name: string;
  description?: string | null;
  sku?: string | null;
  price?: number;
  currency?: string;
  billing_type?: BillingType;
  category_id?: number | null;
  is_active?: boolean;
}

export const catalogApi = {
  listCategories: () => client.get<CatalogCategory[]>("/api/catalog/categories").then((r) => r.data),
  createCategory: (data: CatalogCategoryInput) =>
    client.post<CatalogCategory>("/api/catalog/categories", data).then((r) => r.data),
  updateCategory: (id: number, data: Partial<CatalogCategoryInput>) =>
    client.patch<CatalogCategory>(`/api/catalog/categories/${id}`, data).then((r) => r.data),
  removeCategory: (id: number) => client.delete(`/api/catalog/categories/${id}`),

  listItems: (params: { category_id?: number; include_inactive?: boolean } = {}) =>
    client.get<CatalogItem[]>("/api/catalog/items", { params }).then((r) => r.data),
  createItem: (data: CatalogItemInput) => client.post<CatalogItem>("/api/catalog/items", data).then((r) => r.data),
  updateItem: (id: number, data: Partial<CatalogItemInput>) =>
    client.patch<CatalogItem>(`/api/catalog/items/${id}`, data).then((r) => r.data),
  removeItem: (id: number) => client.delete(`/api/catalog/items/${id}`),
};
