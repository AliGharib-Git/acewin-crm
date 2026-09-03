import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Award,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Download,
  Lock,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import toast from "react-hot-toast";
import { LineChart, Line, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";
import { Badge, Button, Card, Input, Modal, PageSpinner, Select, Textarea } from "../components/ui";
import { okrsApi } from "../api/okrs";
import { usersApi } from "../api/users";
import { entitlementError, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import type { TranslationKey } from "../i18n/translations";
import type { KeyResult, KeyResultUpdateEntry, Objective, ObjectiveStatus, OkrRiskLevel } from "../types";

const STATUS_LABEL_KEYS: Record<ObjectiveStatus, TranslationKey> = {
  draft: "okr.statusDraft",
  active: "okr.statusActive",
  completed: "okr.statusCompleted",
  archived: "okr.statusArchived",
};

const DEPARTMENT_LABEL_KEYS: Record<string, TranslationKey> = {
  sales: "okr.sales",
  operations: "okr.operations",
  general: "okr.general",
};

const RISK_COLORS: Record<OkrRiskLevel, string> = {
  on_track: "#14D9A6",
  at_risk: "#22F0C2",
  critical: "#F2555B",
  draft: "#93A6A6",
  archived: "#93A6A6",
};

const STATUS_COLORS: Record<ObjectiveStatus, string> = {
  draft: "#93A6A6",
  active: "#22D3EE",
  completed: "#14D9A6",
  archived: "#93A6A6",
};

const DEPARTMENTS = ["sales", "operations", "general"];
const STATUSES: ObjectiveStatus[] = ["draft", "active", "completed", "archived"];

function scoreColor(value: number | null): string {
  if (value == null) return "#93A6A6";
  if (value >= 85) return "#14D9A6";
  if (value >= 60) return "#22F0C2";
  return "#F2555B";
}

function currentQuarterKey(): string {
  const now = new Date();
  const quarter = Math.floor(now.getMonth() / 3) + 1;
  return `${now.getFullYear()}-Q${quarter}`;
}

function shiftQuarterKey(periodKey: string, direction: 1 | -1): string {
  const match = /^(\d{4})-Q([1-4])$/.exec(periodKey.trim());
  if (!match) return periodKey;
  let year = Number(match[1]);
  let quarter = Number(match[2]) + direction;
  if (quarter < 1) {
    quarter = 4;
    year -= 1;
  } else if (quarter > 4) {
    quarter = 1;
    year += 1;
  }
  return `${year}-Q${quarter}`;
}

function useTimeAgo() {
  const { t, language } = useLanguage();
  return (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days <= 0) return t("common.today");
    if (days === 1) return t("common.yesterday");
    if (days < 30) return t("common.daysAgo", { days });
    return new Date(dateStr).toLocaleDateString(language === "fa" ? "fa-IR" : undefined);
  };
}

function formatKrNumber(value: number, unit?: string | null): string {
  const rounded = value.toLocaleString(undefined, { maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 1 });
  const u = (unit ?? "").trim();
  if (!u || u.toLowerCase() === "number") return rounded;
  if (u === "%" || u.toLowerCase() === "percent") return `${rounded}%`;
  if (u === "$" || u.toLowerCase() === "usd" || u.toLowerCase() === "currency") return `$${rounded}`;
  return `${rounded} ${u}`;
}

function exportObjectivesCsv(objectives: Objective[]) {
  const header = [
    "department",
    "objective",
    "status",
    "risk_level",
    "score_pct",
    "expected_pct",
    "gap_pct",
    "key_result",
    "kr_current",
    "kr_target",
    "kr_score_pct",
    "linked_kpi",
  ];
  const rows: string[] = [];
  objectives.forEach((o) => {
    if (o.key_results.length === 0) {
      rows.push([o.department, o.title, o.status, o.risk_level, o.score_pct, o.expected_pct, o.gap_pct, "", "", "", "", ""].join(","));
      return;
    }
    o.key_results.forEach((kr) => {
      rows.push(
        [
          o.department,
          o.title,
          o.status,
          o.risk_level,
          o.score_pct,
          o.expected_pct,
          o.gap_pct,
          kr.title,
          kr.current_value ?? "",
          kr.target_value ?? "",
          kr.score_pct,
          kr.linked_kpi_key ?? "",
        ]
          .map((v) => `"${String(v).replace(/"/g, '""')}"`)
          .join(",")
      );
    });
  });
  const csv = [header.join(","), ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `okrs-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function ProgressBar({ value, expected, color }: { value: number; expected?: number; color: string }) {
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-border">
      <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, Math.max(0, value))}%`, backgroundColor: color }} />
      {expected != null && (
        <div className="absolute top-0 h-full w-0.5 bg-accent" style={{ left: `${Math.min(100, Math.max(0, expected))}%` }} />
      )}
    </div>
  );
}

function RiskBadge({ level }: { level: OkrRiskLevel }) {
  const { t } = useLanguage();
  const RISK_LABEL_KEYS: Record<OkrRiskLevel, TranslationKey> = {
    on_track: "okr.riskOnTrack",
    at_risk: "okr.riskAtRisk",
    critical: "okr.riskCritical",
    draft: "okr.riskDraft",
    archived: "okr.riskArchived",
  };
  const labelKey = RISK_LABEL_KEYS[level];
  const Icon = level === "critical" || level === "at_risk" ? AlertTriangle : CheckCircle2;
  return (
    <Badge color={RISK_COLORS[level]}>
      <Icon className="h-3 w-3" />
      {t(labelKey)}
    </Badge>
  );
}

// Objective.status is a separate axis from risk_level: a "completed"
// objective with a low final score still shows risk "at_risk", which on
// its own looks identical to an active objective that's merely behind
// schedule. This pill makes status visible whenever it isn't already
// implied by the risk badge (draft/archived risk levels already say so).
function StatusPill({ status }: { status: ObjectiveStatus }) {
  const { t } = useLanguage();
  if (status === "draft" || status === "archived") return null;
  return <Badge color={STATUS_COLORS[status]}>{t(STATUS_LABEL_KEYS[status])}</Badge>;
}

// ---------- Create Objective ----------

function NewObjectiveModal({ periodKey, onClose }: { periodKey: string; onClose: () => void }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [department, setDepartment] = useState("sales");
  const [period, setPeriod] = useState(periodKey);
  const [ownerId, setOwnerId] = useState<number | undefined>(user?.id);

  const { data: users } = useQuery({ queryKey: ["users"], queryFn: usersApi.list });

  const mutation = useMutation({
    mutationFn: () => okrsApi.createObjective({ title, description: description || undefined, department, period_key: period, owner_id: ownerId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] });
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={t("okr.newObjective")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutation.mutate()} isLoading={mutation.isPending} disabled={!title.trim() || !period.trim()}>
            {t("common.create")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Input label={t("common.title")} value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
        <Textarea label={t("common.description")} value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="grid grid-cols-2 gap-3">
          <Select label={t("okr.department")} value={department} onChange={(e) => setDepartment(e.target.value)}>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
          <Input label={t("okr.period")} value={period} onChange={(e) => setPeriod(e.target.value)} hint="YYYY-Q1..Q4" />
        </div>
        <Select label={t("okr.owner")} value={ownerId ?? ""} onChange={(e) => setOwnerId(e.target.value ? Number(e.target.value) : undefined)}>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </Select>
      </div>
    </Modal>
  );
}

// ---------- Create Key Result ----------

function AddKeyResultModal({ objective, onClose }: { objective: Objective; onClose: () => void }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [measurementType, setMeasurementType] = useState<"metric" | "milestone">("metric");
  const [unit, setUnit] = useState("number");
  const [baseline, setBaseline] = useState("0");
  const [target, setTarget] = useState("");
  const [linkedKpi, setLinkedKpi] = useState("");
  const [weight, setWeight] = useState("1");
  const [ownerId, setOwnerId] = useState<number | undefined>(undefined);

  const { data: kpiOptions } = useQuery({ queryKey: ["okr-kpi-options"], queryFn: okrsApi.kpiOptions });
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: usersApi.list });

  const mutation = useMutation({
    mutationFn: () =>
      okrsApi.createKeyResult(objective.id, {
        title,
        measurement_type: measurementType,
        weight: Number(weight) || 1,
        owner_id: ownerId,
        ...(measurementType === "metric"
          ? {
              unit,
              baseline_value: Number(baseline) || 0,
              target_value: target ? Number(target) : undefined,
              linked_kpi_key: linkedKpi || undefined,
            }
          : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] });
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const canSubmit = title.trim() && (measurementType === "milestone" || linkedKpi || target);

  return (
    <Modal
      open
      onClose={onClose}
      title={`${t("okr.addKeyResult")} — ${objective.title}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutation.mutate()} isLoading={mutation.isPending} disabled={!canSubmit}>
            {t("common.add")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Input label={t("common.title")} value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
        <div className="grid grid-cols-2 gap-3">
          <Select label={t("okr.measurementType")} value={measurementType} onChange={(e) => setMeasurementType(e.target.value as "metric" | "milestone")}>
            <option value="metric">{t("okr.metric")}</option>
            <option value="milestone">{t("okr.milestone")}</option>
          </Select>
          <Input label={t("okr.weight")} type="number" min="0.1" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} />
        </div>
        <Select label={t("okr.keyResultOwner")} value={ownerId ?? ""} onChange={(e) => setOwnerId(e.target.value ? Number(e.target.value) : undefined)}>
          <option value="">{t("common.none")}</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </Select>
        {measurementType === "metric" && (
          <>
            <Select label={t("okr.linkedKpi")} value={linkedKpi} onChange={(e) => setLinkedKpi(e.target.value)}>
              <option value="">{t("common.none")}</option>
              {kpiOptions?.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </Select>
            <div className="grid grid-cols-3 gap-3">
              <Input label={t("okr.baseline")} type="number" value={baseline} onChange={(e) => setBaseline(e.target.value)} />
              <Input label={t("okr.target")} type="number" value={target} onChange={(e) => setTarget(e.target.value)} disabled={!!linkedKpi && !target} />
              <Input label={t("okr.unit")} value={unit} onChange={(e) => setUnit(e.target.value)} />
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

// ---------- Record Progress ----------

function ProgressModal({ objective, kr, onClose }: { objective: Objective; kr: KeyResult; onClose: () => void }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(kr.current_value != null ? String(kr.current_value) : "");
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () => okrsApi.recordProgress(objective.id, kr.id, Number(value), note || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] });
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={`${t("okr.recordProgress")} — ${kr.title}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => mutation.mutate()} isLoading={mutation.isPending} disabled={!value}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Input label={t("okr.progressValue")} type="number" value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
        <Textarea label={t("okr.progressNote")} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
    </Modal>
  );
}

// ---------- Key Result row ----------

function KeyResultHistory({ updates }: { updates: KeyResultUpdateEntry[] }) {
  const { t } = useLanguage();
  const timeAgo = useTimeAgo();
  const sorted = useMemo(
    () => [...updates].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [updates]
  );
  if (sorted.length === 0) {
    return <p className="text-xs italic text-muted">{t("okr.noHistory")}</p>;
  }
  return (
    <ul className="space-y-1.5">
      {sorted.map((u) => (
        <li key={u.id} className="flex items-start justify-between gap-2 text-xs">
          <div className="min-w-0">
            <span className="font-mono font-medium text-ink">{u.value.toLocaleString()}</span>
            {u.note && <span className="ms-1.5 text-muted">— {u.note}</span>}
            {u.created_by_name && <span className="ms-1.5 text-muted">({u.created_by_name})</span>}
          </div>
          <span className="shrink-0 text-muted">{timeAgo(u.created_at)}</span>
        </li>
      ))}
    </ul>
  );
}

function KeyResultRow({ objective, kr, canManage }: { objective: Objective; kr: KeyResult; canManage: boolean }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [progressModal, setProgressModal] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const toggleDoneMutation = useMutation({
    mutationFn: () => okrsApi.updateKeyResult(objective.id, kr.id, { is_done: !kr.is_done }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => okrsApi.deleteKeyResult(objective.id, kr.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const trendData = useMemo(
    () =>
      [...kr.updates]
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        .map((u) => ({ period: u.created_at, value: u.value })),
    [kr.updates]
  );
  const hasTrend = kr.measurement_type === "metric" && trendData.length >= 2;

  return (
    <div className="border-t border-border py-2 first:border-t-0">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-sm text-ink">{kr.title}</p>
            <span className="shrink-0 text-xs font-medium text-muted">{kr.score_pct.toFixed(0)}%</span>
          </div>
          {kr.measurement_type === "metric" ? (
            <>
              <ProgressBar value={kr.score_pct} color="#14D9A6" />
              <p className="mt-0.5 text-[11px] text-muted">
                {kr.current_value != null ? formatKrNumber(kr.current_value, kr.unit) : "—"} /{" "}
                {kr.target_value != null ? formatKrNumber(kr.target_value, kr.unit) : "—"}
                {kr.linked_kpi_key ? ` · ${t("okr.linkedKpiShort")}: ${kr.linked_kpi_key}` : ""}
                {kr.owner ? ` · ${t("okr.owner")}: ${kr.owner.full_name}` : ""}
              </p>
            </>
          ) : (
            <>
              <ProgressBar value={kr.is_done ? 100 : 0} color="#14D9A6" />
              {kr.owner && <p className="mt-0.5 text-[11px] text-muted">{t("okr.owner")}: {kr.owner.full_name}</p>}
            </>
          )}
        </div>
        {canManage && (
          <div className="flex shrink-0 items-center gap-1">
            {kr.measurement_type === "milestone" ? (
              <Button size="sm" variant="secondary" onClick={() => toggleDoneMutation.mutate()} isLoading={toggleDoneMutation.isPending}>
                {kr.is_done ? t("okr.markNotDone") : t("okr.markDone")}
              </Button>
            ) : (
              !kr.linked_kpi_key && (
                <Button size="sm" variant="secondary" onClick={() => setProgressModal(true)}>
                  {t("okr.recordProgress")}
                </Button>
              )
            )}
            <button
              onClick={() => {
                if (window.confirm(t("okr.deleteKeyResultConfirm"))) deleteMutation.mutate();
              }}
              className="rounded p-1 text-muted hover:bg-paper hover:text-danger"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {kr.measurement_type === "metric" && (hasTrend || kr.updates.length > 0) && (
        <div className="mt-1.5">
          {hasTrend && (
            <div className="h-10">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                  <Line type="monotone" dataKey="value" stroke="#14D9A6" strokeWidth={1.5} dot={false} />
                  {kr.target_value != null && <ReferenceLine y={kr.target_value} stroke="#93A6A6" strokeDasharray="3 3" strokeWidth={1} />}
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0D151C", border: "none", borderRadius: 6, color: "#EAF3F0", fontSize: 11, padding: "4px 8px" }}
                    formatter={(v: number) => [formatKrNumber(v, kr.unit), ""]}
                    labelFormatter={() => ""}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className="flex items-center gap-1 text-[11px] font-medium text-muted hover:text-ink"
          >
            {historyOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {historyOpen ? t("okr.hideHistory") : t("okr.checkIns", { n: kr.updates.length })}
          </button>
          {historyOpen && (
            <div className="mt-1.5 rounded-md bg-paper p-2">
              <KeyResultHistory updates={kr.updates} />
            </div>
          )}
        </div>
      )}

      {progressModal && <ProgressModal objective={objective} kr={kr} onClose={() => setProgressModal(false)} />}
    </div>
  );
}

// ---------- Objective card ----------

function ObjectiveCard({
  objective,
  isAdmin,
  currentUserId,
  priorityRank,
}: {
  objective: Objective;
  isAdmin: boolean;
  currentUserId?: number;
  priorityRank?: number;
}) {
  const { t, language } = useLanguage();
  const queryClient = useQueryClient();
  const timeAgo = useTimeAgo();
  const [open, setOpen] = useState(false);
  const [addKrOpen, setAddKrOpen] = useState(false);
  const [explanation, setExplanation] = useState<{ text: string; source: string } | null>(null);

  const isOwner = objective.owner?.id === currentUserId;
  const canManage = isAdmin || isOwner;

  const explainMutation = useMutation({
    mutationFn: () => okrsApi.explain(objective.id, language),
    onSuccess: (res) => setExplanation({ text: res.explanation, source: res.generated_by }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => okrsApi.deleteObjective(objective.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const statusMutation = useMutation({
    mutationFn: (status: ObjectiveStatus) => okrsApi.updateObjective(objective.id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["okr-scoreboard"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const gapLabel =
    objective.risk_level === "at_risk" || objective.risk_level === "critical"
      ? t("okr.gapBehind", { pct: Math.round(objective.gap_pct) })
      : objective.risk_level === "on_track"
        ? t("okr.onPace")
        : null;

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {priorityRank != null && (
              <Badge color="#F2555B">
                <Award className="h-3 w-3" />
                {t("okr.priority")} #{priorityRank}
              </Badge>
            )}
            <Badge color="#93A6A6">{objective.department}</Badge>
            <RiskBadge level={objective.risk_level} />
            <StatusPill status={objective.status} />
          </div>
          <button onClick={() => setOpen((o) => !o)} className="mt-1 flex items-center gap-1.5 text-left">
            <p className="font-display text-base font-medium text-ink">{objective.title}</p>
            <ChevronDown className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
          {objective.description && <p className="mt-0.5 text-xs text-muted">{objective.description}</p>}
          <p className="mt-1 text-xs text-muted">
            {t("okr.owner")}: {objective.owner?.full_name ?? t("common.unassigned")}
            {objective.days_remaining != null && objective.days_remaining >= 0 && ` · ${objective.days_remaining} ${t("okr.daysRemaining")}`}
            {" · "}
            {t("okr.updated")} {timeAgo(objective.updated_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {canManage && (
            <select
              value={objective.status}
              onChange={(e) => statusMutation.mutate(e.target.value as ObjectiveStatus)}
              disabled={statusMutation.isPending}
              aria-label={t("okr.changeStatus")}
              className="rounded border border-border bg-surface px-1.5 py-1 text-[11px] text-muted focus:border-primary focus:outline-none"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(STATUS_LABEL_KEYS[s])}
                </option>
              ))}
            </select>
          )}
          {isAdmin && (
            <button
              onClick={() => {
                if (window.confirm(t("okr.deleteObjectiveConfirm"))) deleteMutation.mutate();
              }}
              className="rounded p-1 text-muted hover:bg-paper hover:text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-muted">
          <span className="font-medium text-ink">{objective.score_pct.toFixed(0)}%</span>
          <span>
            {t("okr.expected")}: {objective.expected_pct.toFixed(0)}%{gapLabel ? ` · ${gapLabel}` : ""}
          </span>
        </div>
        <ProgressBar value={objective.score_pct} expected={objective.expected_pct} color={RISK_COLORS[objective.risk_level]} />
      </div>

      {open && (
        <div className="mt-3 border-t border-border pt-3">
          {objective.key_results.map((kr) => (
            <KeyResultRow key={kr.id} objective={objective} kr={kr} canManage={canManage} />
          ))}
          {canManage && (
            <button onClick={() => setAddKrOpen(true)} className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              <Plus className="h-3.5 w-3.5" />
              {t("okr.addKeyResult")}
            </button>
          )}

          <div className="mt-3 border-t border-border pt-3">
            {explanation ? (
              <div>
                <p className="text-xs leading-relaxed text-ink">{explanation.text}</p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-muted">
                  {explanation.source === "ai" ? t("okr.generatedByAi") : t("okr.generatedByRule")}
                </p>
              </div>
            ) : (
              <button
                onClick={() => explainMutation.mutate()}
                disabled={explainMutation.isPending}
                className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline disabled:opacity-50"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {explainMutation.isPending ? t("okr.explaining") : t("okr.explain")}
              </button>
            )}
          </div>
        </div>
      )}

      {addKrOpen && <AddKeyResultModal objective={objective} onClose={() => setAddKrOpen(false)} />}
    </Card>
  );
}

// ---------- Page ----------

export default function Okrs() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [periodKey, setPeriodKey] = useState(currentQuarterKey());
  const [newObjectiveOpen, setNewObjectiveOpen] = useState(false);
  const [department, setDepartment] = useState<"all" | string>("all");
  const [status, setStatus] = useState<"all" | ObjectiveStatus>("all");

  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery({
    queryKey: ["okr-scoreboard", periodKey],
    queryFn: () => okrsApi.scoreboard(periodKey),
    retry: false,
  });

  const entitlement = isError ? entitlementError(error) : null;

  const departmentEntries = useMemo(() => Object.entries(data?.department_scores ?? {}), [data]);

  // Objectives arrive from the backend already sorted worst-risk-first
  // (see rank_by_priority in the OKR engine) -- this map just labels the
  // top few so that ordering is visible, not only implicit. Ranks are
  // only meaningful against the unfiltered board, so they're hidden
  // once a department/status filter narrows the list.
  const priorityRanks = useMemo(() => {
    const ranks = new Map<number, number>();
    let rank = 0;
    for (const o of data?.objectives ?? []) {
      if (o.risk_level !== "at_risk" && o.risk_level !== "critical") continue;
      rank += 1;
      if (rank <= 3) ranks.set(o.id, rank);
    }
    return ranks;
  }, [data]);

  const filtered = useMemo(
    () =>
      (data?.objectives ?? []).filter(
        (o) => (department === "all" || o.department === department) && (status === "all" || o.status === status)
      ),
    [data, department, status]
  );
  const filtersActive = department !== "all" || status !== "all";

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-medium text-ink">{t("okr.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("okr.subtitle")}</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex items-end gap-1">
            <button
              type="button"
              onClick={() => setPeriodKey((p) => shiftQuarterKey(p, -1))}
              aria-label={t("okr.prevPeriod")}
              className="rounded border border-border bg-surface p-2 text-muted hover:bg-paper"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <Input label={t("okr.period")} value={periodKey} onChange={(e) => setPeriodKey(e.target.value)} className="w-24" />
            <button
              type="button"
              onClick={() => setPeriodKey((p) => shiftQuarterKey(p, 1))}
              aria-label={t("okr.nextPeriod")}
              className="rounded border border-border bg-surface p-2 text-muted hover:bg-paper"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          <Select label={t("okr.filterDepartment")} value={department} onChange={(e) => setDepartment(e.target.value)} className="min-w-[9rem]">
            <option value="all">{t("okr.allDepartments")}</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {t(DEPARTMENT_LABEL_KEYS[d])}
              </option>
            ))}
          </Select>
          <Select label={t("okr.filterStatus")} value={status} onChange={(e) => setStatus(e.target.value as "all" | ObjectiveStatus)} className="min-w-[9rem]">
            <option value="all">{t("common.allStatuses")}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(STATUS_LABEL_KEYS[s])}
              </option>
            ))}
          </Select>
          {data && data.objectives.length > 0 && (
            <Button variant="secondary" onClick={() => exportObjectivesCsv(filtered)} className="gap-1.5">
              <Download className="h-3.5 w-3.5" />
              {t("okr.export")}
            </Button>
          )}
          {isAdmin && (
            <Button onClick={() => setNewObjectiveOpen(true)}>
              <Plus className="h-4 w-4" />
              {t("okr.newObjective")}
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-6">
          <PageSpinner />
        </div>
      ) : entitlement ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <Lock className="h-6 w-6 text-muted" />
          <p className="font-display text-base font-medium text-ink">{t("okr.upgradeRequiredTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{t("okr.upgradeRequiredDesc")}</p>
          <Link to="/pricing">
            <Button className="mt-2">{t("pricing.ctaPro")}</Button>
          </Link>
        </Card>
      ) : isError ? (
        <Card className="mt-6 flex flex-col items-center gap-2 p-8 text-center">
          <AlertTriangle className="h-6 w-6 text-[#F2555B]" />
          <p className="font-display text-base font-medium text-ink">{t("okr.loadErrorTitle")}</p>
          <p className="max-w-sm text-sm text-muted">{errorMessage(error)}</p>
          <Button className="mt-2" variant="secondary" onClick={() => refetch()} isLoading={isRefetching}>
            {t("common.retry")}
          </Button>
        </Card>
      ) : !data ? (
        <div className="mt-6">
          <PageSpinner />
        </div>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap gap-3">
            <Card className="flex min-w-[140px] flex-col p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">{t("okr.companyScore")}</p>
              <p className="mt-1 font-mono text-2xl font-semibold" style={{ color: scoreColor(data.company_score) }}>
                {data.company_score != null ? `${data.company_score.toFixed(0)}%` : "—"}
              </p>
            </Card>
            {departmentEntries.map(([dept, score]) => (
              <Card key={dept} className="flex min-w-[140px] flex-col p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">{dept}</p>
                <p className="mt-1 font-mono text-2xl font-semibold" style={{ color: scoreColor(score) }}>
                  {score != null ? `${score.toFixed(0)}%` : "—"}
                </p>
              </Card>
            ))}
          </div>

          <div className="mt-6 space-y-4">
            {data.objectives.length === 0 ? (
              <p className="text-sm text-muted">{t("okr.noObjectives")}</p>
            ) : filtered.length === 0 ? (
              <p className="text-sm text-muted">{t("okr.emptyFilter")}</p>
            ) : (
              filtered.map((objective) => (
                <ObjectiveCard
                  key={objective.id}
                  objective={objective}
                  isAdmin={isAdmin}
                  currentUserId={user?.id}
                  priorityRank={filtersActive ? undefined : priorityRanks.get(objective.id)}
                />
              ))
            )}
          </div>
        </>
      )}

      {newObjectiveOpen && <NewObjectiveModal periodKey={periodKey} onClose={() => setNewObjectiveOpen(false)} />}
    </div>
  );
}
