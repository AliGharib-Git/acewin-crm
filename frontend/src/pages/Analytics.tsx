import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Flame, Sparkles, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, ModelAccuracyGauge, PageSpinner } from "../components/ui";
import type { ModelMetrics } from "../types";
import { analyticsApi } from "../api/analytics";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";

/**
 * Shown instead of a spinner once a query has actually failed (e.g. the
 * backend returns 503 because backend/data/olist/*.csv is missing) --
 * without this, `isLoading || !data` (used by every card below) stays
 * true forever on error, since react-query sets isLoading back to
 * false but never populates `data`. Mirrors the isError branch already
 * used in Kpis.tsx / Okrs.tsx / Gamification.tsx.
 */
function ErrorState({ fa, error, onRetry, isRetrying }: { fa: boolean; error: unknown; onRetry: () => void; isRetrying: boolean }) {
  return (
    <Card className="flex flex-col items-center gap-2 p-8 text-center">
      <AlertTriangle className="h-6 w-6 text-[#F2555B]" />
      <p className="font-display text-base font-medium text-ink">{fa ? "بارگذاری این بخش ممکن نشد" : "Couldn't load this section"}</p>
      <p className="max-w-sm text-sm text-muted">{errorMessage(error)}</p>
      <Button className="mt-2" variant="secondary" onClick={onRetry} isLoading={isRetrying}>
        {fa ? "تلاش مجدد" : "Try again"}
      </Button>
    </Card>
  );
}

function SectionHeader({ icon: Icon, title, why }: { icon: React.ElementType; title: string; why?: string }) {
  return (
    <div className="mb-3 flex items-start justify-between gap-4">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-primary" />
        <h2 className="font-display text-base font-medium text-ink">{title}</h2>
      </div>
      {why && <p className="max-w-sm text-right text-xs text-muted">{why}</p>}
    </div>
  );
}

function KpiPill({ kpi, value, status }: { kpi: string; value: string | number; status: string }) {
  const colors: Record<string, string> = { good: "#14D9A6", warning: "#22F0C2", critical: "#F2555B" };
  return (
    <div className="rounded border border-border bg-surface p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{kpi}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-ink">{value}</p>
      <span className="mt-1 inline-block h-1.5 w-8 rounded-full" style={{ backgroundColor: colors[status] ?? "#93A6A6" }} />
    </div>
  );
}

const tooltipStyle = {
  backgroundColor: "#0D151C",
  border: "none",
  borderRadius: 6,
  color: "#EAF3F0",
  fontSize: 12,
  padding: "8px 12px",
};

function ForecastChart() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["analytics", "revenue-forecast", language],
    queryFn: () => analyticsApi.revenueForecast(3, language),
    retry: false,
  });
  if (isError) return <ErrorState fa={fa} error={error} onRetry={() => refetch()} isRetrying={isRefetching} />;
  if (isLoading || !data) return <PageSpinner />;
  const backtestByMonth = new Map(data.backtest.map((b) => [b.month, b.predicted_revenue]));
  const chartData = [
    ...data.history.slice(-9).map((h) => ({
      month: h.month,
      actual: h.revenue,
      forecast: null as number | null,
      modeled: backtestByMonth.get(h.month) ?? null,
    })),
    ...data.forecast.map((f) => ({ month: f.month, actual: null as number | null, forecast: f.predicted_revenue, modeled: null as number | null })),
  ];
  return (
    <Card className="p-4">
      <SectionHeader icon={TrendingUp} title={fa ? "پیش‌بینی درآمد" : "Revenue forecast"} why={data.why} />
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#16262A" vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#93A6A6" }} axisLine={{ stroke: "#16262A" }} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: "#93A6A6" }} axisLine={false} tickLine={false} width={60} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="actual" name={fa ? "واقعی" : "Actual"} stroke="#14D9A6" strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} />
          <Line
            type="monotone"
            dataKey="modeled"
            name={fa ? "پیش‌بینیِ مدل (گذشته)" : "Model's prediction (past)"}
            stroke="#93A6A6"
            strokeWidth={1.75}
            strokeDasharray="2 3"
            dot={{ r: 2 }}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            name={fa ? "پیش‌بینی آینده" : "Forecast (future)"}
            stroke="#22F0C2"
            strokeWidth={2.5}
            strokeDasharray="5 4"
            dot={{ r: 3 }}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-muted">
        {fa
          ? `خط خاکستری نشون می‌ده مدل برای همون ماه‌های گذشته چی پیش‌بینی می‌کرد؛ در مقایسه با خط سبز (واقعیت)، به‌طور میانگین ${data.backtest_mape}% فاصله وجود داشت.`
          : `The gray line is what the model would have predicted for each past month; compared to the green (actual) line, predictions were off by ${data.backtest_mape}% on average.`}
      </p>
      <p className="mt-1 text-xs text-muted">{data.business_impact}</p>
      <div className="mt-3">
        <ModelAccuracyGauge metrics={data.model_metrics} lang={language} />
      </div>
    </Card>
  );
}

function ChurnCard() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["analytics", "churn", language],
    queryFn: () => analyticsApi.churn(180, language),
    retry: false,
  });
  if (isError) return <ErrorState fa={fa} error={error} onRetry={() => refetch()} isRetrying={isRefetching} />;
  if (isLoading || !data) return <PageSpinner />;
  return (
    <Card className="p-4">
      <SectionHeader icon={AlertTriangle} title={fa ? "ریسک ریزش" : "Churn risk"} why={data.why} />
      <p className="font-mono text-3xl font-semibold text-ink">{(data.overall_churn_rate * 100).toFixed(1)}%</p>
      <p className="text-xs text-muted">{fa ? `مشتریان تکراریِ غیرفعال برای ${data.churn_window_days}+ روز` : `of repeat customers inactive ${data.churn_window_days}+ days`}</p>
      <div className="mt-3 space-y-1.5">
        {data.at_risk_customers.slice(0, 5).map((c) => (
          <div key={c.customer_unique_id} className="flex items-center justify-between gap-2 text-xs">
            <span className="font-mono text-muted">{c.customer_unique_id.slice(0, 10)}…</span>
            <span className="flex-1 truncate text-ink">{c.state_name}</span>
            <span className="font-medium text-ink">{(c.churn_probability * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <ModelAccuracyGauge metrics={data.model_metrics} lang={language} />
      </div>
    </Card>
  );
}

function LeadScoringCard() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["analytics", "lead-scoring", language],
    queryFn: () => analyticsApi.leadScoring(5, language),
    retry: false,
  });
  if (isError) return <ErrorState fa={fa} error={error} onRetry={() => refetch()} isRetrying={isRefetching} />;
  if (isLoading || !data) return <PageSpinner />;
  const chartData = [...data.leads]
    .sort((a, b) => a.lead_score - b.lead_score)
    .map((l) => ({ label: `${l.customer_unique_id.slice(0, 6)}… · ${l.state}`, score: l.lead_score }));
  return (
    <Card className="p-4">
      <SectionHeader icon={Flame} title={fa ? "امتیازدهی سرنخ" : "Lead scoring"} why={data.why} />
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 24, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#16262A" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: "#93A6A6" }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={90} tick={{ fontSize: 10, fill: "#93A6A6", fontFamily: "IBM Plex Mono, monospace" }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(0)}`, fa ? "امتیاز" : "Score"]} />
          <Bar dataKey="score" radius={[0, 4, 4, 0]}>
            {chartData.map((d) => (
              <Cell key={d.label} fill={d.score >= 75 ? "#14D9A6" : d.score >= 40 ? "#22F0C2" : "#F2555B"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-3 space-y-1.5">
        {data.leads.map((l) => (
          <div key={l.customer_unique_id} className="flex items-center justify-between gap-2 text-xs">
            <span className="font-mono text-muted">{l.customer_unique_id.slice(0, 10)}…</span>
            <span className="flex-1 truncate text-ink">
              {l.state_name} · ${l.total_spent.toFixed(0)} · {l.order_count} {fa ? "سفارش" : "orders"}
            </span>
            <span className="font-mono font-semibold text-ink">{l.lead_score.toFixed(0)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <ModelAccuracyGauge metrics={data.model_metrics} lang={language} />
      </div>
    </Card>
  );
}

function ModelAccuracySummary() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const { data: forecast } = useQuery({ queryKey: ["analytics", "revenue-forecast", language], queryFn: () => analyticsApi.revenueForecast(3, language) });
  const { data: churn } = useQuery({ queryKey: ["analytics", "churn", language], queryFn: () => analyticsApi.churn(180, language) });
  const { data: lead } = useQuery({ queryKey: ["analytics", "lead-scoring", language], queryFn: () => analyticsApi.leadScoring(5, language) });

  const rows: { label: string; metrics?: ModelMetrics }[] = [
    { label: fa ? "پیش‌بینی درآمد" : "Revenue forecast", metrics: forecast?.model_metrics },
    { label: fa ? "ریسک ریزش" : "Churn risk", metrics: churn?.model_metrics },
    { label: fa ? "امتیازدهی سرنخ" : "Lead scoring", metrics: lead?.model_metrics },
  ];

  return (
    <Card className="p-4">
      <SectionHeader icon={BarChart3} title={fa ? "خلاصهٔ دقت مدل‌ها" : "Model accuracy summary"} />
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {rows.map((r) => {
          const m = r.metrics;
          const trained = m?.trained;
          const isR2 = m?.metric_name === "r2";
          const displayValue = trained
            ? `${isR2 ? "R² " : ""}${Math.round((m!.metric_value ?? 0) * 100)}%`
            : fa
              ? "در حال محاسبه…"
              : "…";
          return (
            <div key={r.label} className="rounded border border-border bg-surface p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">{r.label}</p>
              <p className="mt-1 font-mono text-lg font-semibold text-ink">{displayValue}</p>
              <p className="mt-0.5 truncate text-[11px] text-muted">{m?.algorithm ?? "—"}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function Analytics() {
  const { t, language } = useLanguage();
  const fa = language === "fa";
  const {
    data: exec,
    isLoading: execLoading,
    isError: execIsError,
    error: execError,
    refetch: execRefetch,
    isRefetching: execIsRefetching,
  } = useQuery({
    queryKey: ["analytics", "executive", language],
    queryFn: () => analyticsApi.executiveInsights(language),
    retry: false,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 font-display text-2xl font-medium text-ink">
          <BarChart3 className="h-5 w-5 text-primary" />
          {t("nav.analytics")}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {fa ? "بینش تجاری تولیدشده توسط موتور تحلیل ACEWIN بر پایهٔ تاریخچهٔ واقعی سفارش مشتریان." : "Business intelligence generated by the ACEWIN Analytics Engine, trained and validated on real customer order history."}
        </p>
      </div>

      {execIsError ? (
        <ErrorState fa={fa} error={execError} onRetry={() => execRefetch()} isRetrying={execIsRefetching} />
      ) : execLoading || !exec ? (
        <PageSpinner />
      ) : (
        <Card className="border-l-4 border-l-primary bg-gradient-to-br from-primary-light/60 to-surface p-4">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            {fa ? "خلاصهٔ هوشمند این هفته" : "This week's smart summary"}
          </div>
          <p className="mt-1.5 font-display text-lg font-medium leading-snug text-ink">{exec.narrative}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {exec.highlights.map((h) => (
              <span key={h} className="rounded-full border border-primary/25 bg-surface px-3 py-1 text-xs font-medium text-primary-dark">
                {h}
              </span>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {exec.kpis.map((k) => (
              <KpiPill key={k.kpi} kpi={k.kpi} value={k.value} status={k.status} />
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{exec.recommended_action}</p>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ForecastChart />
        <ChurnCard />
        <LeadScoringCard />
      </div>

      <ModelAccuracySummary />
    </div>
  );
}
