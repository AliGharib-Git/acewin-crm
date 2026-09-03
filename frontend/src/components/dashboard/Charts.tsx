import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { useLanguage } from "../../context/LanguageContext";
import type { FunnelStage, RevenuePoint, WonLostPoint } from "../../types";

function useCurrencyFormatter() {
  const { language } = useLanguage();
  return new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  });
}

function useMonthLabel() {
  const { language } = useLanguage();
  return (period: string) => {
    const [year, month] = period.split("-");
    const date = new Date(Number(year), Number(month) - 1, 1);
    return date.toLocaleDateString(language === "fa" ? "fa-IR" : "en-US", { month: "short" });
  };
}

const tooltipStyle = {
  backgroundColor: "#0D151C",
  border: "none",
  borderRadius: 6,
  color: "#EAF3F0",
  fontFamily: "IBM Plex Sans, sans-serif",
  fontSize: 12,
  padding: "8px 12px",
};

export function RevenueTrendChart({ data }: { data: RevenuePoint[] }) {
  const { t } = useLanguage();
  const currencyFormatter = useCurrencyFormatter();
  const monthLabel = useMonthLabel();
  const chartData = data.map((d) => ({ ...d, label: monthLabel(d.period) }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#16262A" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#93A6A6" }} axisLine={{ stroke: "#16262A" }} tickLine={false} />
        <YAxis
          tick={{ fontSize: 11, fill: "#93A6A6" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => currencyFormatter.format(v)}
          width={56}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number) => [currencyFormatter.format(value), t("settings.won")]}
          labelFormatter={(label) => label}
        />
        <Line type="monotone" dataKey="won_value" stroke="#14D9A6" strokeWidth={2.5} dot={{ r: 3, fill: "#14D9A6" }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function PipelineFunnelChart({ data }: { data: FunnelStage[] }) {
  const { language } = useLanguage();
  const currencyFormatter = useCurrencyFormatter();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#16262A" vertical={false} />
        <XAxis
          dataKey="stage_name"
          tick={{ fontSize: 11, fill: "#93A6A6" }}
          axisLine={{ stroke: "#16262A" }}
          tickLine={false}
          interval={0}
          angle={language === "fa" ? 15 : -15}
          textAnchor="end"
          height={50}
        />
        <YAxis tick={{ fontSize: 11, fill: "#93A6A6" }} axisLine={false} tickLine={false} width={30} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number, name: string, entry) => [
            `${value} · ${currencyFormatter.format(entry.payload.value)}`,
            "",
          ]}
          labelFormatter={(label) => label}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.stage_id} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function WonLostChart({ data }: { data: WonLostPoint[] }) {
  const { t } = useLanguage();
  const monthLabel = useMonthLabel();
  const chartData = data.map((d) => ({ ...d, label: monthLabel(d.period) }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#16262A" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#93A6A6" }} axisLine={{ stroke: "#16262A" }} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: "#93A6A6" }} axisLine={false} tickLine={false} width={30} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="won_count" name={t("settings.won")} fill="#14D9A6" radius={[4, 4, 0, 0]} />
        <Bar dataKey="lost_count" name={t("settings.lost")} fill="#F2555B" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

