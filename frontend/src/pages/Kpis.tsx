import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  HelpCircle,
  Lock,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import toast from "react-hot-toast";
import { LineChart, Line, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";
import { Badge, Button, Card, Input, Modal, PageSpinner, Select } from "../components/ui";
import { kpisApi } from "../api/kpis";
import { entitlementError, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import type { TranslationKey } from "../i18n/translations";
import type { KPI } from "../types";

const RISK_COLORS: Record<string, string> = {
  on_track: "#14D9A6",
  at_risk: "#22F0C2",
  critical: "#F2555B",
  unknown: "#93A6A6",
};

const RISK_ICON: Record<string, React.ElementType> = {
  on_track: CheckCircle2,
  at_risk: AlertTriangle,
  critical: AlertTriangle,
  unknown: HelpCircle,
};

const RANGE_OPTIONS = [3, 6, 12, 24];

function formatValue(value: number, unit: KPI["unit"]) {
  if (unit === "currency") {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(value);
  }
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "days") return `${value.toFixed(1)}d`;
  if (unit === "hours") return `${value.toFixed(1)}h`;
  return value.toLocaleString();
}

function volatilityLabel(
  pct: number | null,
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string,
): { label: string; color: string } {
  if (pct == null) return { label: "—", color: "#93A6A6" };
  if (pct < 15) return { label: t("kpi.riskOnTrack"), color: "#14D9A6" };
  if (pct < 40) return { label: t("kpi.riskAtRisk"), color: "#22F0C2" };
  return { label: t("kpi.riskCritical"), color: "#F2555B" };
}

function TargetModal({ kpi, months, onClose }: { kpi: KPI; months: number; onClose: () => void }) {
  const { t, language } = useLanguage();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(kpi.target != null ? String(kpi.target) : "");

  const mutation = useMutation({
    mutationFn: () => kpisApi.setTarget(kpi.key, Number(value), language),
    onSuccess: () => {
      toast.success(t("kpi.targetSaved"));
      queryClient.invalidateQueries({ queryKey: ["kpis", language, months] });
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={`${t("kpi.setTarget")} — ${kpi.name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutation.mutate()} isLoading={mutation.isPending} disabled={!value || Number(value) <= 0}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <Input
        type="number"
        min="0"
        step="any"
        label={t("kpi.targetPlaceholder")}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
    </Modal>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-muted">{label}</span>
      <span className="font-mono text-sm font-medium text-ink">{value}</span>
    </div>
  );
}

function KpiCard({ kpi, isAdmin, onSetTarget }: { kpi: KPI; isAdmin: boolean; onSetTarget: (kpi: KPI) => void }) {
  const { t, language } = useLanguage();
  const [explanation, setExplanation] = useState<{ text: string; source: string } | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const explainMutation = useMutation({
    mutationFn: () => kpisApi.explain(kpi.key, language),
    onSuccess: (res) => setExplanation({ text: res.explanation, source: res.generated_by }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const RiskIcon = RISK_ICON[kpi.risk_level];
  const riskLabelKey = (
    {
      on_track: "kpi.riskOnTrack",
      at_risk: "kpi.riskAtRisk",
      critical: "kpi.riskCritical",
      unknown: "kpi.riskUnknown",
    } satisfies Record<KPI["risk_level"], TranslationKey>
  )[kpi.risk_level];

  const trendUp = kpi.change_pct != null && kpi.change_pct > 0;
  const isGoodChange = kpi.change_pct != null && (trendUp === kpi.higher_is_better);
  const vol = kpi.stats ? volatilityLabel(kpi.stats.volatility_pct, t) : null;
  const hasDetails = !!kpi.stats || !!(kpi.breakdown && kpi.breakdown.length > 0) || kpi.prediction_low != null;

  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{kpi.name}</p>
          <p className="mt-1 font-mono text-2xl font-semibold text-ink">{formatValue(kpi.current_value, kpi.unit)}</p>
        </div>
        <Badge color={RISK_COLORS[kpi.risk_level]}>
          <RiskIcon className="h-3 w-3" />
          {t(riskLabelKey)}
        </Badge>
      </div>

      {kpi.description && <p className="mt-1 text-[11px] leading-relaxed text-muted">{kpi.description}</p>}

      {kpi.change_pct != null && (
        <div className="mt-1 flex items-center gap-1 text-xs" style={{ color: isGoodChange ? "#14D9A6" : "#F2555B" }}>
          {trendUp ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
          {kpi.change_pct > 0 ? "+" : ""}
          {kpi.change_pct}%
        </div>
      )}

      {kpi.supports_trend && kpi.trend && kpi.trend.length > 1 ? (
        <div className="mt-3 h-16">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={kpi.trend} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
              <Line type="monotone" dataKey="value" stroke="#14D9A6" strokeWidth={2} dot={false} />
              {kpi.stats && <ReferenceLine y={kpi.stats.mean} stroke="#93A6A6" strokeDasharray="3 3" strokeWidth={1} />}
              <Tooltip
                contentStyle={{ backgroundColor: "#0D151C", border: "none", borderRadius: 6, color: "#EAF3F0", fontSize: 11, padding: "4px 8px" }}
                formatter={(v: number) => [formatValue(v, kpi.unit), ""]}
                labelFormatter={() => ""}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-xs italic text-muted">{t("kpi.snapshotNote")}</p>
      )}

      {kpi.prediction_next != null && (
        <p className="mt-2 text-xs text-muted">
          {t("kpi.prediction")}: <span className="font-medium text-ink">{formatValue(kpi.prediction_next, kpi.unit)}</span>
          {kpi.prediction_low != null && kpi.prediction_high != null && (
            <span className="text-muted">
              {" "}
              ({t("kpi.confidenceRange")}: {formatValue(kpi.prediction_low, kpi.unit)}–{formatValue(kpi.prediction_high, kpi.unit)})
            </span>
          )}
        </p>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-xs">
        <div className="text-muted">
          {t("kpi.target")}:{" "}
          {kpi.target != null ? <span className="font-medium text-ink">{formatValue(kpi.target, kpi.unit)}</span> : t("kpi.noTarget")}
        </div>
        {isAdmin && (
          <button onClick={() => onSetTarget(kpi)} className="font-medium text-primary hover:underline">
            {kpi.target != null ? t("kpi.editTarget") : t("kpi.setTarget")}
          </button>
        )}
      </div>

      {hasDetails && (
        <div className="mt-3 border-t border-border pt-3">
          <button
            onClick={() => setDetailsOpen((v) => !v)}
            className="flex w-full items-center justify-between text-xs font-medium text-ink"
          >
            {t("kpi.details")}
            {detailsOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {detailsOpen && (
            <div className="mt-3 space-y-3">
              {kpi.stats && (
                <div className="grid grid-cols-4 gap-2 rounded-md bg-paper p-2">
                  <StatRow label={t("kpi.statsMean")} value={formatValue(kpi.stats.mean, kpi.unit)} />
                  <StatRow label={t("kpi.statsMedian")} value={formatValue(kpi.stats.median, kpi.unit)} />
                  <StatRow label={t("kpi.statsMin")} value={formatValue(kpi.stats.min, kpi.unit)} />
                  <StatRow label={t("kpi.statsMax")} value={formatValue(kpi.stats.max, kpi.unit)} />
                </div>
              )}
              {vol && kpi.stats?.volatility_pct != null && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted">{t("kpi.statsVolatility")}</span>
                  <span className="font-medium" style={{ color: vol.color }}>
                    {kpi.stats.volatility_pct}%
                  </span>
                </div>
              )}
              <div>
                <p className="mb-1.5 flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted">
                  <Users className="h-3 w-3" />
                  {t("kpi.topContributors")}
                </p>
                {kpi.breakdown && kpi.breakdown.length > 0 ? (
                  <div className="space-y-1">
                    {kpi.breakdown.map((entry) => {
                      const max = kpi.breakdown![0].value || 1;
                      const pct = Math.max(4, Math.round((entry.value / max) * 100));
                      return (
                        <div key={entry.label} className="flex items-center gap-2 text-xs">
                          <span className="w-20 shrink-0 truncate text-ink">{entry.label}</span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-paper">
                            <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-16 shrink-0 text-end font-mono text-muted">
                            {kpi.unit === "currency" ? formatValue(entry.value, "currency") : entry.value.toLocaleString()}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs italic text-muted">{t("kpi.noBreakdown")}</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-3 border-t border-border pt-3">
        {explanation ? (
          <div>
            <p className="text-xs leading-relaxed text-ink">{explanation.text}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-muted">
              {explanation.source === "ai" ? t("kpi.generatedByAi") : t("kpi.generatedByRule")}
            </p>
          </div>
        ) : (
          <button
            onClick={() => explainMutation.mutate()}
            disabled={explainMutation.isPending}
            className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {explainMutation.isPending ? t("kpi.explaining") : t("kpi.explain")}
          </button>
        )}
      </div>
    </Card>
  );
}

function exportCsv(kpis: KPI[]) {
  const header = ["key", "name", "department", "unit", "current_value", "previous_value", "change_pct", "target", "risk_level", "prediction_next"];
  const rows = kpis.map((k) =>
    [k.key, k.name, k.department, k.unit, k.current_value, k.previous_value ?? "", k.change_pct ?? "", k.target ?? "", k.risk_level, k.prediction_next ?? ""]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(",")
  );
  const csv = [header.join(","), ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `kpis-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function Kpis() {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [targetModalKpi, setTargetModalKpi] = useState<KPI | null>(null);
  const [months, setMonths] = useState(6);
  const [department, setDepartment] = useState<"all" | "sales" | "operations">("all");

  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["kpis", language, months],
    queryFn: () => kpisApi.list(language, months),
    retry: false,
  });

  const entitlement = isError ? entitlementError(error) : null;
  const filtered = useMemo(() => (data ?? []).filter((k) => department === "all" || k.department === department), [data, department]);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-medium text-ink">{t("kpi.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("kpi.subtitle")}</p>
        </div>
        {data && (
          <div className="flex flex-wrap items-end gap-2">
            <Select label={t("kpi.range")} value={months} onChange={(e) => setMonths(Number(e.target.value))} className="min-w-[9rem]">
              {RANGE_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {t("kpi.rangeMonths", { n: m })}
                </option>
              ))}
            </Select>
            <Select
              label={t("kpi.department")}
              value={department}
              onChange={(e) => setDepartment(e.target.value as "all" | "sales" | "operations")}
              className="min-w-[9rem]"
            >
              <option value="all">{t("kpi.allDepartments")}</option>
              <option value="sales">{t("kpi.sales")}</option>
              <option value="operations">{t("kpi.operations")}</option>
            </Select>
            <Button variant="secondary" onClick={() => exportCsv(filtered)} className="gap-1.5">
              <Download className="h-3.5 w-3.5" />
              {t("kpi.export")}
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="mt-6">
          <PageSpinner />
        </div>
      ) : entitlement ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <Lock className="h-6 w-6 text-muted" />
          <p className="font-display text-base font-medium text-ink">{t("kpi.upgradeRequiredTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{t("kpi.upgradeRequiredDesc")}</p>
          <Link to="/pricing">
            <Button className="mt-2">{t("pricing.ctaPro")}</Button>
          </Link>
        </Card>
      ) : isError ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <AlertTriangle className="h-6 w-6 text-[#F2555B]" />
          <p className="font-display text-base font-medium text-ink">{t("kpi.loadErrorTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{errorMessage(error)}</p>
          <Button className="mt-2" variant="secondary" onClick={() => refetch()} isLoading={isRefetching}>
            {t("common.retry")}
          </Button>
        </Card>
      ) : !data ? (
        <div className="mt-6">
          <PageSpinner />
        </div>
      ) : filtered.length === 0 ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <p className="text-sm text-muted">{t("kpi.emptyFilter")}</p>
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} isAdmin={isAdmin} onSetTarget={setTargetModalKpi} />
          ))}
        </div>
      )}

      {targetModalKpi && <TargetModal kpi={targetModalKpi} months={months} onClose={() => setTargetModalKpi(null)} />}
    </div>
  );
}
