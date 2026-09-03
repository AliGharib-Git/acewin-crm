import { client } from "./client";
import type { Company, Page } from "../types";

export interface CompanyInput {
  name: string;
  industry?: string | null;
  website?: string | null;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

export const companiesApi = {
  list: (params: { search?: string; page?: number; page_size?: number } = {}) =>
    client.get<Page<Company>>("/api/companies", { params }).then((r) => r.data),
  get: (id: number) => client.get<Company>(`/api/companies/${id}`).then((r) => r.data),
  create: (data: CompanyInput) => client.post<Company>("/api/companies", data).then((r) => r.data),
  update: (id: number, data: Partial<CompanyInput>) =>
    client.patch<Company>(`/api/companies/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/companies/${id}`),
};
