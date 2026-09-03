import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Users, Building2, Target, CheckCircle2, AlertCircle, TrendingUp, Trophy } from "lucide-react";
import { Card, PageSpinner, StatusBadge } from "../components/ui";
import { RevenueTrendChart, PipelineFunnelChart, WonLostChart } from "../components/dashboard/Charts";
import { dashboardApi } from "../api/dashboard";
import { tasksApi } from "../api/tasks";
import { gamificationApi } from "../api/gamification";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";

function GamificationWidget() {
  const { t, language } = useLanguage();
  const { data } = useQuery({
    queryKey: ["gamification", "me", language],
    queryFn: () => gamificationApi.me(language),
    retry: false,
  });

  // A Basic-plan org gets a 402 here, or an admin may have gamification
  // switched off -- both are expected states, not errors to surface on
  // the dashboard, so the widget just quietly hides itself.
  if (!data || !data.enabled) return null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-base font-medium text-ink">{t("gamification.dashboardWidgetTitle")}</h3>
        <Trophy className="h-4 w-4 text-[#22F0C2]" />
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div>
          <p className="font-display text-xl font-medium text-ink">
            {t("gamification.level")} {data.level} — {data.level_title}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {data.total_points} {data.token_name ?? t("gamification.points")} · {t("gamification.weeklyRank")}{" "}
            {data.weekly_rank ? `#${data.weekly_rank}` : t("gamification.unranked")}
          </p>
        </div>
        <Link to="/gamification" className="text-xs font-medium text-primary hover:underline">
          {t("gamification.viewLeaderboard")}
        </Link>
      </div>
    </Card>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
        <Icon className="h-4 w-4" style={{ color: accent ?? "#93A6A6" }} />
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold tabular text-ink">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t, language } = useLanguage();
  const currencyFormatter = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.summary,
  });
  const { data: revenue } = useQuery({ queryKey: ["dashboard", "revenue"], queryFn: () => dashboardApi.revenueTrend(6) });
  const { data: funnel } = useQuery({ queryKey: ["dashboard", "funnel"], queryFn: dashboardApi.funnel });
  const { data: wonLost } = useQuery({ queryKey: ["dashboard", "won-lost"], queryFn: () => dashboardApi.wonLost(6) });
  const { data: upcomingTasks } = useQuery({
    queryKey: ["tasks", "upcoming"],
    queryFn: () => tasksApi.list({ status: "pending", page_size: 6 }),
  });

  if (loadingSummary || !summary) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">
          {t("dashboard.welcomeBack")}{user ? `, ${user.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("dashboard.pipelineToday")}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={Target}
          label={t("dashboard.openPipeline")}
          value={currencyFormatter.format(summary.open_deals_value)}
          sub={t("dashboard.openDealsCount", { count: summary.open_deals_count })}
          accent="#14D9A6"
        />
        <StatCard
          icon={TrendingUp}
          label={t("dashboard.wonThisMonth")}
          value={currencyFormatter.format(summary.won_this_month_value)}
          sub={t("dashboard.dealsClosedCount", { count: summary.won_this_month_count })}
          accent="#22F0C2"
        />
        <StatCard
          icon={Users}
          label={t("dashboard.totalContacts")}
          value={String(summary.total_contacts)}
          sub={t("dashboard.companiesCount", { count: summary.total_companies })}
        />
        <StatCard
          icon={summary.overdue_tasks > 0 ? AlertCircle : CheckCircle2}
          label={t("dashboard.tasks")}
          value={String(summary.tasks_due_today)}
          sub={t("dashboard.dueTodayOverdue", { count: summary.overdue_tasks })}
          accent={summary.overdue_tasks > 0 ? "#F2555B" : "#14D9A6"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="font-display text-base font-medium text-ink">{t("dashboard.revenueTrend")}</h3>
          <p className="text-xs text-muted">{t("dashboard.revenueTrendSub")}</p>
          <div className="mt-2">{revenue ? <RevenueTrendChart data={revenue} /> : <PageSpinner />}</div>
        </Card>
        <Card className="p-5">
          <h3 className="font-display text-base font-medium text-ink">{t("dashboard.pipelineByStage")}</h3>
          <p className="text-xs text-muted">{t("dashboard.dealCountPerStage")}</p>
          <div className="mt-2">{funnel ? <PipelineFunnelChart data={funnel} /> : <PageSpinner />}</div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="font-display text-base font-medium text-ink">{t("dashboard.wonVsLost")}</h3>
            <p className="text-xs text-muted">{t("dashboard.dealsClosedPerMonth")}</p>
            <div className="mt-2">{wonLost ? <WonLostChart data={wonLost} /> : <PageSpinner />}</div>
          </Card>
          <GamificationWidget />
        </div>
        <Card className="p-5">
          <h3 className="font-display text-base font-medium text-ink">{t("dashboard.upcomingTasks")}</h3>
          <p className="text-xs text-muted">{t("dashboard.nextPendingItems")}</p>
          <div className="mt-3 space-y-2">
            {upcomingTasks?.items.length === 0 && <p className="text-sm text-muted">{t("dashboard.nothingPending")}</p>}
            {upcomingTasks?.items.map((task) => (
              <div key={task.id} className="flex items-center justify-between border-b border-border py-2 last:border-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{task.title}</p>
                  <p className="text-xs text-muted">
                    {task.due_date ? new Date(task.due_date).toLocaleDateString(language === "fa" ? "fa-IR" : undefined) : t("tasks.noDueDate")}
                    {task.contact_name ? ` · ${task.contact_name}` : ""}
                  </p>
                </div>
                <StatusBadge value={task.priority} label={t(`common.${task.priority}` as "common.low")} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
