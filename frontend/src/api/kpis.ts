import { client } from "./client";
import type { KPI, KPIExplanation } from "../types";

export const kpisApi = {
  list: (lang: "en" | "fa", months = 6) =>
    client.get<KPI[]>("/api/kpis", { params: { lang, months } }).then((r) => r.data),
  get: (key: string, lang: "en" | "fa", months = 6) =>
    client.get<KPI>(`/api/kpis/${key}`, { params: { lang, months } }).then((r) => r.data),
  setTarget: (key: string, targetValue: number, lang: "en" | "fa") =>
    client.put<KPI>(`/api/kpis/${key}/target`, { target_value: targetValue }, { params: { lang } }).then((r) => r.data),
  explain: (key: string, lang: "en" | "fa") =>
    client.post<KPIExplanation>(`/api/kpis/${key}/explain`, undefined, { params: { lang } }).then((r) => r.data),
};
