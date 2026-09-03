import { client } from "./client";
import type {
  BillingCycle,
  Page,
  PlanTier,
  PlatformActionLog,
  PlatformFeedback,
  PlatformOrganization,
  PlatformOrganizationDetail,
  PlatformSalesLead,
  PlatformSupportRequest,
  SubscriptionStatus,
  SupportRequestStatus,
} from "../types";

export const platformAdminApi = {
  listOrganizations: () => client.get<PlatformOrganization[]>("/api/platform-admin/organizations").then((r) => r.data),

  getOrganization: (orgId: number) =>
    client.get<PlatformOrganizationDetail>(`/api/platform-admin/organizations/${orgId}`).then((r) => r.data),

  setStatus: (orgId: number, is_active: boolean) =>
    client.patch<PlatformOrganization>(`/api/platform-admin/organizations/${orgId}/status`, { is_active }).then((r) => r.data),

  updateSubscription: (
    orgId: number,
    payload: {
      plan?: PlanTier;
      status?: SubscriptionStatus;
      billing_cycle?: BillingCycle;
      trial_ends_at?: string | null;
      clear_trial_end?: boolean;
    }
  ) => client.patch<PlatformOrganization>(`/api/platform-admin/organizations/${orgId}/subscription`, payload).then((r) => r.data),

  approveTrial: (orgId: number) =>
    client.post<PlatformOrganization>(`/api/platform-admin/organizations/${orgId}/subscription/approve-trial`).then((r) => r.data),

  updateLimitOverrides: (orgId: number, overrides: Record<string, number>) =>
    client.patch<PlatformOrganization>(`/api/platform-admin/organizations/${orgId}/limits`, { overrides }).then((r) => r.data),

  updateFeatureOverrides: (orgId: number, overrides: Record<string, boolean>) =>
    client.patch<PlatformOrganization>(`/api/platform-admin/organizations/${orgId}/features`, { overrides }).then((r) => r.data),

  // Requests tab: manual support requests + the automatic cross-tenant action feed.
  listRequests: (status?: SupportRequestStatus) =>
    client
      .get<PlatformSupportRequest[]>("/api/platform-admin/requests", { params: status ? { status } : undefined })
      .then((r) => r.data),

  updateRequest: (requestId: number, payload: { status?: SupportRequestStatus; admin_reply?: string }) =>
    client.patch<PlatformSupportRequest>(`/api/platform-admin/requests/${requestId}`, payload).then((r) => r.data),

  // Feedback sub-tab: anonymous comments/complaints filed from the public homepage.
  listFeedback: (status?: SupportRequestStatus) =>
    client
      .get<PlatformFeedback[]>("/api/platform-admin/feedback", { params: status ? { status } : undefined })
      .then((r) => r.data),

  updateFeedback: (feedbackId: number, payload: { status?: SupportRequestStatus; admin_reply?: string }) =>
    client.patch<PlatformFeedback>(`/api/platform-admin/feedback/${feedbackId}`, payload).then((r) => r.data),

  // Sales leads sub-tab: VIP / Enterprise "Contact sales" requests filed
  // from the Pricing page (see app/routers/sales_leads.py).
  listSalesLeads: (status?: SupportRequestStatus) =>
    client
      .get<PlatformSalesLead[]>("/api/platform-admin/sales-leads", { params: status ? { status } : undefined })
      .then((r) => r.data),

  updateSalesLead: (leadId: number, payload: { status?: SupportRequestStatus; admin_reply?: string }) =>
    client.patch<PlatformSalesLead>(`/api/platform-admin/sales-leads/${leadId}`, payload).then((r) => r.data),

  listActions: (params?: { organization_id?: number; source?: string; page?: number; page_size?: number }) =>
    client.get<Page<PlatformActionLog>>("/api/platform-admin/actions", { params }).then((r) => r.data),
};
