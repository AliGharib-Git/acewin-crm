import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { AlertTriangle, Award, ChevronLeft, ChevronRight, Lock, Medal, PowerOff, ShieldCheck, Trophy, Users } from "lucide-react";
import { Button, Card, Input, PageSpinner, Select } from "../components/ui";
import { gamificationApi } from "../api/gamification";
import { entitlementError, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import type { GamificationBadge, LeaderboardPeriod } from "../types";

/** The org's custom currency label + icon (e.g. "سکه اکرمی" / "🪙"),
 * with a sane fallback while it's loading or gamification is off.
 * Backed by the same cached ["gamification","me",language] query
 * ProfileCard already fetches, so this never costs an extra request. */
function useToken() {
  const { t, language } = useLanguage();
  const { data } = useQuery({ queryKey: ["gamification", "me", language], queryFn: () => gamificationApi.me(language), retry: false });
  return { name: data?.token_name ?? t("gamification.points"), icon: data?.token_icon ?? "🏆" };
}

function ProgressBar({ value, color = "#14D9A6" }: { value: number; color?: string }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-border">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${Math.min(100, Math.max(0, value * 100))}%`, backgroundColor: color }}
      />
    </div>
  );
}

function ProfileCard() {
  const { t, language } = useLanguage();
  const { data } = useQuery({ queryKey: ["gamification", "me", language], queryFn: () => gamificationApi.me(language), retry: false });
  if (!data || !data.enabled) return null;
  const tokenName = data.token_name ?? t("gamification.points");
  const tokenIcon = data.token_icon ?? "🏆";

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{t("gamification.yourLevel")}</p>
          <p className="mt-1 font-display text-2xl font-medium text-ink">
            {t("gamification.level")} {data.level} — {data.level_title}
          </p>
        </div>
        <Trophy className="h-8 w-8 text-[#22F0C2]" />
      </div>

      <div className="mt-4">
        <ProgressBar value={data.progress_ratio ?? 0} />
        <p className="mt-1.5 text-xs text-muted">
          {t("gamification.pointsToNext", {
            points: Math.max(0, (data.points_for_next_level ?? 0) - (data.points_in_level ?? 0)),
            level: (data.level ?? 1) + 1,
          })}
        </p>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-3 lg:grid-cols-5">
        <div>
          <p className="text-xs text-muted">
            {tokenIcon} {tokenName}
          </p>
          <p className="mt-0.5 font-mono text-lg font-medium text-ink">{data.total_points}</p>
        </div>
        <div>
          <p className="text-xs text-muted">{t("gamification.weeklyPoints")}</p>
          <p className="mt-0.5 font-mono text-lg font-medium text-ink">
            {data.weekly_points} <span className="text-xs font-normal text-muted">{data.weekly_rank ? `#${data.weekly_rank}` : t("gamification.unranked")}</span>
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">{t("gamification.monthlyPoints")}</p>
          <p className="mt-0.5 font-mono text-lg font-medium text-ink">
            {data.monthly_points} <span className="text-xs font-normal text-muted">{data.monthly_rank ? `#${data.monthly_rank}` : t("gamification.unranked")}</span>
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">{t("gamification.badges")}</p>
          <p className="mt-0.5 font-mono text-lg font-medium text-ink">{data.badge_count}</p>
        </div>
        <div>
          <p className="text-xs text-muted" title={t("gamification.taskFollowThroughHint")}>
            {t("gamification.taskFollowThrough")}
          </p>
          <p className="mt-0.5 font-mono text-lg font-medium text-ink">
            {data.tasks_total ? `${data.tasks_completed}/${data.tasks_total}` : "—"}
            {!!data.tasks_overdue && (
              <span className="ms-1.5 text-xs font-medium text-[#F2555B]">
                {t("gamification.overdueCount", { count: data.tasks_overdue })}
              </span>
            )}
          </p>
        </div>
      </div>
    </Card>
  );
}

function LeaderboardCard() {
  const { t, language } = useLanguage();
  const token = useToken();
  const [period, setPeriod] = useState<LeaderboardPeriod>("weekly");

  const { data, isLoading } = useQuery({
    queryKey: ["gamification", "leaderboard", period, language],
    queryFn: () => gamificationApi.leaderboard(period, language),
    retry: false,
  });

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-base font-medium text-ink">{t("gamification.leaderboard")}</h2>
        <Select value={period} onChange={(e) => setPeriod(e.target.value as LeaderboardPeriod)} className="!w-auto py-1 text-xs">
          <option value="weekly">{t("gamification.periodWeekly")}</option>
          <option value="monthly">{t("gamification.periodMonthly")}</option>
          <option value="all_time">{t("gamification.periodAllTime")}</option>
        </Select>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <PageSpinner />
        ) : !data || data.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t("gamification.noEntries")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {data.map((entry) => (
              <li
                key={entry.user_id}
                className={`flex items-center gap-3 py-2.5 ${entry.is_you ? "rounded-md bg-primary/5 px-2" : ""}`}
              >
                <span className="w-6 shrink-0 text-center font-mono text-sm text-muted">
                  {entry.rank <= 3 ? <Medal className="mx-auto h-4 w-4" style={{ color: ["#22F0C2", "#93A6A6", "#93A6A6"][entry.rank - 1] }} /> : entry.rank}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">
                    {entry.full_name} {entry.is_you && <span className="text-xs font-normal text-primary">({t("gamification.you")})</span>}
                  </p>
                  <p className="text-xs text-muted">
                    {t("gamification.yourLevel")} {entry.level} — {entry.level_title}
                  </p>
                </div>
                <span className="shrink-0 font-mono text-sm font-medium text-ink">
                  {entry.points} <span className="text-xs">{token.icon}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function BadgeTile({ badge }: { badge: GamificationBadge }) {
  const { t } = useLanguage();
  return (
    <div className={`flex flex-col items-center gap-2 rounded-lg border p-4 text-center ${badge.earned ? "border-border bg-surface" : "border-border/60 bg-paper"}`}>
      <div className="relative">
        <Award className="h-7 w-7" style={{ color: badge.earned ? "#22F0C2" : "#93A6A6" }} />
        {!badge.earned && (
          <span className="absolute -end-1.5 -top-1.5 rounded-full bg-paper p-0.5">
            <Lock className="h-3 w-3 text-muted" />
          </span>
        )}
      </div>
      <div>
        <p className={`text-xs font-medium ${badge.earned ? "text-ink" : "text-muted"}`}>{badge.name}</p>
        {/* The description is the badge's criteria (e.g. "Closed 10 won
            deals") -- always shown, locked or not, since hiding it behind
            a generic "not earned yet" is exactly what makes badges feel
            opaque. Locked ones just get a status line appended. */}
        <p className="mt-0.5 text-[11px] leading-snug text-muted">{badge.description}</p>
        <p className={`mt-1 text-[10px] font-medium ${badge.earned ? "text-[#14D9A6]" : "text-muted"}`}>
          {badge.earned ? t("gamification.badgeEarned") : t("gamification.badgeLocked")}
        </p>
      </div>
    </div>
  );
}

function BadgesCard() {
  const { t, language } = useLanguage();
  const { data, isLoading } = useQuery({ queryKey: ["gamification", "badges", language], queryFn: () => gamificationApi.badges(language), retry: false });

  return (
    <Card className="p-5">
      <h2 className="font-display text-base font-medium text-ink">{t("gamification.badges")}</h2>
      <p className="mt-0.5 text-xs text-muted">{t("gamification.badgesSubtitle")}</p>
      <div className="mt-4">
        {isLoading ? (
          <PageSpinner />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {(data ?? []).map((badge) => (
              <BadgeTile key={badge.code} badge={badge} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function HistoryCard() {
  const { t, language } = useLanguage();
  const token = useToken();
  const { data, isLoading } = useQuery({
    queryKey: ["gamification", "ledger", language],
    queryFn: () => gamificationApi.ledger(1, 15, language),
    retry: false,
  });

  return (
    <Card className="p-5">
      <h2 className="font-display text-base font-medium text-ink">{t("gamification.history")}</h2>
      <div className="mt-3">
        {isLoading ? (
          <PageSpinner />
        ) : !data || data.items.length === 0 ? (
          <p className="py-4 text-sm text-muted">{t("gamification.historyEmpty")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {data.items.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p className="text-ink">{entry.reason}</p>
                  <p className="text-xs text-muted">{new Date(entry.created_at).toLocaleString(language === "fa" ? "fa-IR" : "en-US")}</p>
                </div>
                <span className={`font-mono font-medium ${entry.points >= 0 ? "text-[#14D9A6]" : "text-[#F2555B]"}`}>
                  {entry.points >= 0 ? "+" : ""}
                  {entry.points} <span className="text-xs">{token.icon}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function AdminSettingsCard() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["gamification", "settings"], queryFn: gamificationApi.getSettings, retry: false });

  const mutation = useMutation({
    mutationFn: gamificationApi.updateSettings,
    onSuccess: () => {
      toast.success(t("gamification.settingsSaved"));
      queryClient.invalidateQueries({ queryKey: ["gamification"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  // Local draft state for the free-text token fields so a keystroke
  // doesn't fire a PUT request per character -- committed onBlur.
  const [tokenNameEn, setTokenNameEn] = useState<string | null>(null);
  const [tokenNameFa, setTokenNameFa] = useState<string | null>(null);
  const [tokenIcon, setTokenIcon] = useState<string | null>(null);

  if (!data) return null;

  return (
    <Card className="p-5">
      <h2 className="font-display text-base font-medium text-ink">{t("gamification.adminSettings")}</h2>
      <div className="mt-4 space-y-4">
        <label className="flex items-center justify-between gap-3 text-sm">
          <span className="text-ink">{t("gamification.enableToggle")}</span>
          <input
            type="checkbox"
            checked={data.enabled}
            onChange={(e) => mutation.mutate({ enabled: e.target.checked })}
            className="h-4 w-4 accent-primary"
          />
        </label>

        <div>
          <p className="text-sm text-ink">{t("gamification.defaultPeriod")}</p>
          <Select
            className="mt-1.5"
            value={data.leaderboard_default_period}
            onChange={(e) => mutation.mutate({ leaderboard_default_period: e.target.value as LeaderboardPeriod })}
          >
            <option value="weekly">{t("gamification.periodWeekly")}</option>
            <option value="monthly">{t("gamification.periodMonthly")}</option>
            <option value="all_time">{t("gamification.periodAllTime")}</option>
          </Select>
        </div>

        <label className="flex items-center justify-between gap-3 text-sm">
          <span className="text-ink">{t("gamification.includeAdmins")}</span>
          <input
            type="checkbox"
            checked={data.include_admins_in_leaderboard}
            onChange={(e) => mutation.mutate({ include_admins_in_leaderboard: e.target.checked })}
            className="h-4 w-4 accent-primary"
          />
        </label>

        <div className="border-t border-border pt-4">
          <p className="text-sm text-ink">{t("gamification.tokenIcon")}</p>
          <p className="mt-0.5 text-xs text-muted">{t("gamification.tokenHint")}</p>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Input
              label={t("gamification.tokenIcon")}
              value={tokenIcon ?? data.token_icon}
              maxLength={8}
              onChange={(e) => setTokenIcon(e.target.value)}
              onBlur={() => tokenIcon !== null && tokenIcon !== data.token_icon && mutation.mutate({ token_icon: tokenIcon })}
            />
            <Input
              label={t("gamification.tokenNameFa")}
              value={tokenNameFa ?? data.token_name_fa}
              maxLength={40}
              onChange={(e) => setTokenNameFa(e.target.value)}
              onBlur={() => tokenNameFa !== null && tokenNameFa !== data.token_name_fa && mutation.mutate({ token_name_fa: tokenNameFa })}
            />
            <Input
              label={t("gamification.tokenNameEn")}
              value={tokenNameEn ?? data.token_name_en}
              maxLength={40}
              onChange={(e) => setTokenNameEn(e.target.value)}
              onBlur={() => tokenNameEn !== null && tokenNameEn !== data.token_name_en && mutation.mutate({ token_name_en: tokenNameEn })}
            />
          </div>
        </div>
      </div>
    </Card>
  );
}

function AdminOverviewCard() {
  const { t, language } = useLanguage();
  const token = useToken();
  const { data, isLoading } = useQuery({
    queryKey: ["gamification", "admin", "users", language],
    queryFn: () => gamificationApi.adminUsers(language),
    retry: false,
  });

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <Users className="h-4 w-4 text-muted" />
        <h2 className="font-display text-base font-medium text-ink">{t("gamification.adminOverview")}</h2>
      </div>
      <div className="mt-4 overflow-x-auto">
        {isLoading ? (
          <PageSpinner />
        ) : !data || data.length === 0 ? (
          <p className="py-4 text-sm text-muted">{t("gamification.noEntries")}</p>
        ) : (
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-start text-xs text-muted">
                <th className="py-2 text-start font-medium">{t("gamification.tableUser")}</th>
                <th className="py-2 text-start font-medium">{t("gamification.tableLevel")}</th>
                <th className="py-2 text-end font-medium" title={t("gamification.taskFollowThroughHint")}>
                  {t("gamification.tableFollowThrough")}
                </th>
                <th className="py-2 text-end font-medium">{t("gamification.tableWeekly")}</th>
                <th className="py-2 text-end font-medium">{t("gamification.tableMonthly")}</th>
                <th className="py-2 text-end font-medium">{t("gamification.tableTotal")}</th>
                <th className="py-2 text-end font-medium">{t("gamification.tableBadges")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((row) => (
                <tr key={row.user_id}>
                  <td className="py-2.5">
                    <p className="font-medium text-ink">{row.full_name}</p>
                  </td>
                  <td className="py-2.5 text-muted">
                    {row.level} — {row.level_title}
                  </td>
                  <td className="py-2.5 text-end">
                    <span className="font-mono text-ink">{row.tasks_total ? `${row.tasks_completed}/${row.tasks_total}` : "—"}</span>
                    {!!row.tasks_overdue && (
                      <span className="ms-1.5 rounded-full bg-[#F2555B]/10 px-1.5 py-0.5 text-[10px] font-medium text-[#F2555B]">
                        {t("gamification.overdueCount", { count: row.tasks_overdue })}
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 text-end font-mono text-ink">{row.weekly_points}</td>
                  <td className="py-2.5 text-end font-mono text-ink">{row.monthly_points}</td>
                  <td className="py-2.5 text-end font-mono font-medium text-ink">
                    {row.total_points} <span className="text-xs">{token.icon}</span>
                  </td>
                  <td className="py-2.5 text-end font-mono text-ink">{row.badge_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

const SOURCE_TYPES = ["deal_won", "task_completed", "activity_logged", "contact_converted", "streak_bonus", "team_assist"] as const;

function AdminLedgerCard() {
  const { t, language } = useLanguage();
  const token = useToken();
  const [page, setPage] = useState(1);
  const [sourceType, setSourceType] = useState<string>("");
  const pageSize = 15;

  const { data, isLoading } = useQuery({
    queryKey: ["gamification", "admin", "ledger", page, sourceType, language],
    queryFn: () => gamificationApi.adminLedger(page, pageSize, language, { sourceType: sourceType || undefined }),
    retry: false,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted" />
          <h2 className="font-display text-base font-medium text-ink">{t("gamification.adminLedgerTitle")}</h2>
        </div>
        <Select
          value={sourceType}
          onChange={(e) => {
            setSourceType(e.target.value);
            setPage(1);
          }}
          className="!w-auto py-1 text-xs"
        >
          <option value="">{t("gamification.filterAllSources")}</option>
          {SOURCE_TYPES.map((st) => (
            <option key={st} value={st}>
              {t(`gamification.source.${st}` as "gamification.source.deal_won")}
            </option>
          ))}
        </Select>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <PageSpinner />
        ) : !data || data.items.length === 0 ? (
          <p className="py-4 text-sm text-muted">{t("gamification.adminLedgerEmpty")}</p>
        ) : (
          <>
            <ul className="divide-y divide-border">
              {data.items.map((entry) => (
                <li key={entry.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate text-ink">
                      <span className="font-medium">{entry.full_name}</span> — {entry.reason}
                    </p>
                    <p className="text-xs text-muted">{new Date(entry.created_at).toLocaleString(language === "fa" ? "fa-IR" : "en-US")}</p>
                  </div>
                  <span className={`shrink-0 font-mono font-medium ${entry.points >= 0 ? "text-[#14D9A6]" : "text-[#F2555B]"}`}>
                    {entry.points >= 0 ? "+" : ""}
                    {entry.points} <span className="text-xs">{token.icon}</span>
                  </span>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-border pt-3 mt-2">
              <span className="text-xs text-muted">{t("common.pageOf", { page, total: totalPages })}</span>
              <div className="flex gap-1">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded p-1.5 text-muted hover:bg-paper disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded p-1.5 text-muted hover:bg-paper disabled:opacity-40"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

export default function Gamification() {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["gamification", "me", language],
    queryFn: () => gamificationApi.me(language),
    retry: false,
  });

  const entitlement = isError ? entitlementError(error) : null;

  return (
    <div>
      <h1 className="font-display text-xl font-medium text-ink">{t("gamification.title")}</h1>
      <p className="mt-1 text-sm text-muted">{t("gamification.subtitle")}</p>

      {isLoading ? (
        <div className="mt-6">
          <PageSpinner />
        </div>
      ) : entitlement ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <Lock className="h-6 w-6 text-muted" />
          <p className="font-display text-base font-medium text-ink">{t("gamification.upgradeRequiredTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{t("gamification.upgradeRequiredDesc")}</p>
          <Link to="/pricing">
            <Button className="mt-2">{t("pricing.ctaPro")}</Button>
          </Link>
        </Card>
      ) : isError ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <AlertTriangle className="h-6 w-6 text-[#F2555B]" />
          <p className="font-display text-base font-medium text-ink">{t("gamification.loadErrorTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{errorMessage(error)}</p>
          <Button className="mt-2" variant="secondary" onClick={() => refetch()} isLoading={isRefetching}>
            {t("common.retry")}
          </Button>
        </Card>
      ) : data && !data.enabled ? (
        <div className="mt-6 space-y-4">
          <Card className="flex flex-col items-center gap-2 p-8 text-center">
            <PowerOff className="h-6 w-6 text-muted" />
            <p className="font-display text-base font-medium text-ink">{t("gamification.disabledTitle")}</p>
            <p className="max-w-sm text-sm text-muted">{t("gamification.disabledDesc")}</p>
          </Card>
          {isAdmin && <AdminSettingsCard />}
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          <ProfileCard />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <LeaderboardCard />
            <HistoryCard />
          </div>
          <BadgesCard />
          {isAdmin && (
            <>
              <AdminOverviewCard />
              <AdminLedgerCard />
              <AdminSettingsCard />
            </>
          )}
        </div>
      )}
    </div>
  );
}
