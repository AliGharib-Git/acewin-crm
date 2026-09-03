import { client } from "./client";
import type { DashboardSummary, FunnelStage, RevenuePoint, WonLostPoint } from "../types";

export const dashboardApi = {
  summary: () => client.get<DashboardSummary>("/api/dashboard/summary").then((r) => r.data),
  funnel: () => client.get<FunnelStage[]>("/api/dashboard/pipeline-funnel").then((r) => r.data),
  revenueTrend: (months = 6) =>
    client.get<RevenuePoint[]>("/api/dashboard/revenue-trend", { params: { months } }).then((r) => r.data),
  wonLost: (months = 6) =>
    client.get<WonLostPoint[]>("/api/dashboard/deals-won-lost", { params: { months } }).then((r) => r.data),
};
