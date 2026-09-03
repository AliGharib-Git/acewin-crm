import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Combines clsx (conditional classes) with tailwind-merge (resolves conflicting
// Tailwind utilities by keeping the last one, e.g. a passed-in `className` correctly
// overrides a variant's default color instead of both classes landing in the DOM
// and the winner being decided by unpredictable CSS generation order).
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(...inputs));
}
import { Loader2, X } from "lucide-react";

// ---------- Button ----------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md";
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", isLoading, className, children, disabled, ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center gap-2 rounded font-medium transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap";
    const sizes = size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-sm";
    const variants: Record<string, string> = {
      primary: "bg-primary text-black hover:bg-primary-dark",
      secondary: "bg-surface text-ink border border-border hover:bg-paper",
      danger: "bg-danger text-white hover:bg-danger/90",
      ghost: "bg-transparent text-ink hover:bg-white/5",
    };
    return (
      <button
        ref={ref}
        className={cn(base, sizes, variants[variant], className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

// ---------- Card ----------

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("bg-surface border border-border rounded shadow-card", className)}>{children}</div>;
}

// ---------- Input / Textarea / Select ----------

interface FieldWrapperProps {
  label?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

function FieldWrapper({ label, error, hint, required, children }: FieldWrapperProps) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-sm font-medium text-ink">
          {label} {required && <span className="text-danger">*</span>}
        </span>
      )}
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

const fieldClass =
  "w-full rounded border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary transition-colors";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, hint, required, className, ...props }, ref) => (
  <FieldWrapper label={label} error={error} hint={hint} required={required}>
    <input ref={ref} className={cn(fieldClass, className)} {...props} />
  </FieldWrapper>
));
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, required, className, ...props }, ref) => (
    <FieldWrapper label={label} error={error} hint={hint} required={required}>
      <textarea ref={ref} className={cn(fieldClass, "resize-none", className)} rows={3} {...props} />
    </FieldWrapper>
  )
);
Textarea.displayName = "Textarea";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hint, required, className, children, ...props }, ref) => (
    <FieldWrapper label={label} error={error} hint={hint} required={required}>
      <select ref={ref} className={cn(fieldClass, "bg-surface", className)} {...props}>
        {children}
      </select>
    </FieldWrapper>
  )
);
Select.displayName = "Select";

// ---------- Badge ----------

export function Badge({ color = "#93A6A6", children }: { color?: string; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: `${color}1A`, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {children}
    </span>
  );
}

const STATUS_COLORS: Record<string, string> = {
  lead: "#93A6A6",
  prospect: "#22D3EE",
  customer: "#14D9A6",
  inactive: "#93A6A6",
  low: "#93A6A6",
  medium: "#22F0C2",
  high: "#F2555B",
  pending: "#22F0C2",
  completed: "#14D9A6",
  pending_trial: "#F2A93B",
  trialing: "#22F0C2",
  active: "#14D9A6",
  past_due: "#F2555B",
  canceled: "#93A6A6",
};

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  const color = STATUS_COLORS[value] ?? "#93A6A6";
  const text = label ?? value.charAt(0).toUpperCase() + value.slice(1);
  return <Badge color={color}>{text}</Badge>;
}

// ---------- Model accuracy gauge ----------
// The one place in the Analytics page that answers, in a single glance,
// "how good is the model that's actually running behind this number?" --
// every value it shows comes straight from a held-out test set the model
// never trained on (see model_metrics in the API response).

import type { ModelMetrics } from "../types";

const GAUGE_R = 26;
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_R;

export function ModelAccuracyGauge({ metrics, lang = "en" }: { metrics?: ModelMetrics | null; lang?: "en" | "fa" }) {
  const fa = lang === "fa";
  if (!metrics) return null;

  if (!metrics.trained) {
    return (
      <div className="flex items-center gap-2 rounded border border-dashed border-border px-3 py-2 text-xs text-muted">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted" />
        {fa ? "هنوز داده کافی برای فیت مدل واقعی نیست" : "Not enough data yet to fit a real model"}
      </div>
    );
  }

  const isR2 = metrics.metric_name === "r2";
  const pct = Math.round(Math.max(0, Math.min(1, metrics.metric_value ?? 0)) * 100);
  const color = pct >= 75 ? "#14D9A6" : pct >= 50 ? "#22F0C2" : "#F2555B";
  const offset = GAUGE_CIRCUMFERENCE * (1 - pct / 100);

  const metricLabel = isR2 ? "R²" : fa ? "دقت" : "Accuracy";
  const displayValue = isR2 ? `${Math.round((metrics.metric_value ?? 0) * 100)}%` : `${pct}%`;
  const secondaryLabel =
    metrics.secondary_metric_name === "mae"
      ? fa
        ? `خطای میانگین $${metrics.secondary_metric_value}`
        : `avg. error $${metrics.secondary_metric_value}`
      : metrics.secondary_metric_name === "roc_auc"
        ? `AUC ${metrics.secondary_metric_value}`
        : metrics.secondary_metric_name === "mape"
          ? fa
            ? `اختلاف پیش‌بینی با واقعیت ${metrics.secondary_metric_value}%`
            : `predicted-vs-actual gap ${metrics.secondary_metric_value}%`
          : null;

  return (
    <div className="flex items-center gap-3 rounded border border-border bg-surface p-3">
      <svg width="64" height="64" viewBox="0 0 64 64" className="shrink-0 -rotate-90">
        <circle cx="32" cy="32" r={GAUGE_R} fill="none" stroke="#16262A" strokeWidth="6" />
        <circle
          cx="32"
          cy="32"
          r={GAUGE_R}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={GAUGE_CIRCUMFERENCE}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
        <text
          x="32"
          y="32"
          textAnchor="middle"
          dominantBaseline="central"
          className="rotate-90"
          style={{ transform: "rotate(90deg)", transformOrigin: "32px 32px", fontSize: 15, fontWeight: 600, fill: "#0D151C", fontFamily: "IBM Plex Mono, monospace" }}
        >
          {displayValue}
        </text>
      </svg>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">
          {fa ? `${metricLabel} مدل روی داده‌ی آزمون` : `Model ${metricLabel} on held-out data`}
        </p>
        <p className="truncate text-sm font-medium text-ink">{metrics.algorithm}</p>
        <p className="text-xs text-muted">
          {secondaryLabel ? `${secondaryLabel} · ` : ""}
          {fa ? `${metrics.test_size} نمونهٔ آزمون` : `${metrics.test_size} test samples`}
        </p>
      </div>
    </div>
  );
}

// ---------- Modal ----------

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  if (!open) return null;
  const widths = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl" };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-paper/70 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div
        className={clsx(
          "relative w-full rounded bg-surface shadow-xl max-h-[90vh] flex flex-col",
          widths[size]
        )}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-muted hover:bg-paper hover:text-ink"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}

// ---------- Spinner / Empty state ----------

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-primary", className)} />;
}

export function PageSpinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-dashed border-border px-6 py-16 text-center">
      {icon && <div className="mb-3 text-muted">{icon}</div>}
      <h3 className="font-display text-base font-medium text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
