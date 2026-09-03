import { client } from "./client";

export interface SalesLeadCreatePayload {
  contact_name: string;
  contact_email: string;
  contact_phone?: string | null;
  company_name?: string | null;
  message?: string | null;
}

export interface SalesLeadOut {
  id: number;
  status: string;
  created_at: string;
}

export const salesLeadsApi = {
  /** Files a real "Contact sales" lead from the Pricing page's VIP /
   * Enterprise card -- works whether the caller is signed in or not
   * (client.ts's interceptor attaches the bearer token automatically
   * when one exists; the backend treats a missing/invalid one as an
   * anonymous lead rather than an error). */
  create: (payload: SalesLeadCreatePayload) =>
    client.post<SalesLeadOut>("/api/sales-leads", payload).then((r) => r.data),
};
