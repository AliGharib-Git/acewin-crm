import { client } from "./client";
import type {
  BusinessPerformanceResult,
  ChurnResult,
  ClvResult,
  ExecutiveInsightsResult,
  LeadScoringResult,
  NextBestActionResult,
  RevenueForecastResult,
  RiskDetectionResult,
  SalesTrendResult,
  SegmentationResult,
} from "../types";

type Lang = "en" | "fa";

export const analyticsApi = {
  segmentation: (lang: Lang = "en") =>
    client.get<SegmentationResult>("/api/analytics/segmentation", { params: { lang } }).then((r) => r.data),
  leadScoring: (topN = 10, lang: Lang = "en") =>
    client.get<LeadScoringResult>("/api/analytics/lead-scoring", { params: { top_n: topN, lang } }).then((r) => r.data),
  clv: (topN = 10, lang: Lang = "en") =>
    client.get<ClvResult>("/api/analytics/clv", { params: { top_n: topN, lang } }).then((r) => r.data),
  churn: (windowDays = 180, lang: Lang = "en") =>
    client
      .get<ChurnResult>("/api/analytics/churn", { params: { window_days: windowDays, lang } })
      .then((r) => r.data),
  revenueForecast: (monthsAhead = 3, lang: Lang = "en") =>
    client
      .get<RevenueForecastResult>("/api/analytics/revenue-forecast", { params: { months_ahead: monthsAhead, lang } })
      .then((r) => r.data),
  salesTrends: (lang: Lang = "en") =>
    client.get<SalesTrendResult>("/api/analytics/sales-trends", { params: { lang } }).then((r) => r.data),
  riskDetection: (lang: Lang = "en") =>
    client.get<RiskDetectionResult>("/api/analytics/risk-detection", { params: { lang } }).then((r) => r.data),
  nextBestAction: (lang: Lang = "en") =>
    client.get<NextBestActionResult>("/api/analytics/next-best-action", { params: { lang } }).then((r) => r.data),
  businessPerformance: (lang: Lang = "en") =>
    client
      .get<BusinessPerformanceResult>("/api/analytics/business-performance", { params: { lang } })
      .then((r) => r.data),
  executiveInsights: (lang: Lang = "en") =>
    client
      .get<ExecutiveInsightsResult>("/api/analytics/executive-insights", { params: { lang } })
      .then((r) => r.data),
};
