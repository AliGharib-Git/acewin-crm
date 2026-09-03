import { client } from "./client";
import type { Deal, Page } from "../types";

export interface DealItemInput {
  catalog_item_id?: number | null;
  name?: string | null;
  unit_price?: number | null;
  quantity?: number;
}

export interface DealInput {
  title: string;
  value?: number;
  probability?: number;
  expected_close_date?: string | null;
  notes?: string | null;
  stage_id: number;
  contact_id?: number | null;
  company_id?: number | null;
  assigned_to_id?: number | null;
  items?: DealItemInput[];
}

export const dealsApi = {
  list: (
    params: {
      stage_id?: number;
      assigned_to_id?: number;
      search?: string;
      contact_id?: number;
      company_id?: number;
      page?: number;
      page_size?: number;
    } = {}
  ) => client.get<Page<Deal>>("/api/deals", { params }).then((r) => r.data),
  get: (id: number) => client.get<Deal>(`/api/deals/${id}`).then((r) => r.data),
  create: (data: DealInput) => client.post<Deal>("/api/deals", data).then((r) => r.data),
  update: (id: number, data: Partial<DealInput>) =>
    client.patch<Deal>(`/api/deals/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/deals/${id}`),
};
