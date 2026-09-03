import { client } from "./client";
import type {
  AdminLedgerEntry,
  AdminUserSummary,
  GamificationBadge,
  GamificationSettings,
  GamificationSummary,
  LeaderboardEntry,
  LeaderboardPeriod,
  Page,
  PointsLedgerEntry,
} from "../types";

export const gamificationApi = {
  me: (lang: "en" | "fa") => client.get<GamificationSummary>("/api/gamification/me", { params: { lang } }).then((r) => r.data),
  leaderboard: (period: LeaderboardPeriod, lang: "en" | "fa") =>
    client.get<LeaderboardEntry[]>("/api/gamification/leaderboard", { params: { period, lang } }).then((r) => r.data),
  badges: (lang: "en" | "fa") => client.get<GamificationBadge[]>("/api/gamification/badges", { params: { lang } }).then((r) => r.data),
  ledger: (page: number, pageSize: number, lang: "en" | "fa") =>
    client
      .get<Page<PointsLedgerEntry>>("/api/gamification/ledger", { params: { page, page_size: pageSize, lang } })
      .then((r) => r.data),
  getSettings: () => client.get<GamificationSettings>("/api/gamification/settings").then((r) => r.data),
  updateSettings: (payload: Partial<GamificationSettings>) =>
    client.put<GamificationSettings>("/api/gamification/settings", payload).then((r) => r.data),

  // Admin panel -- org-wide visibility, not just "my own score".
  adminUsers: (lang: "en" | "fa") =>
    client.get<AdminUserSummary[]>("/api/gamification/admin/users", { params: { lang } }).then((r) => r.data),
  adminLedger: (
    page: number,
    pageSize: number,
    lang: "en" | "fa",
    filters?: { userId?: number; sourceType?: string }
  ) =>
    client
      .get<Page<AdminLedgerEntry>>("/api/gamification/admin/ledger", {
        params: { page, page_size: pageSize, lang, user_id: filters?.userId, source_type: filters?.sourceType },
      })
      .then((r) => r.data),
};
