import { client } from "./client";
import type { BillingCycle, Plan, PlanTier, Subscription } from "../types";

export const billingApi = {
  /** Public pricing-page data -- works logged out too. */
  listPlans: () => client.get<Plan[]>("/api/billing/plans").then((r) => r.data),
  /** Same plans, but `is_current` reflects the caller's actual org -- requires auth. */
  comparePlans: () => client.get<Plan[]>("/api/billing/plans/compare").then((r) => r.data),
  getSubscription: () => client.get<Subscription>("/api/billing/subscription").then((r) => r.data),
  changePlan: (plan: PlanTier, billing_cycle: BillingCycle) =>
    client.patch<Subscription>("/api/billing/subscription", { plan, billing_cycle }).then((r) => r.data),
};
