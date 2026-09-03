import { client } from "./client";
import type { KeyResult, Objective, ObjectiveExplanation, OKRScoreboard } from "../types";

export const okrsApi = {
  listObjectives: (periodKey?: string, department?: string) =>
    client.get<Objective[]>("/api/objectives", { params: { period_key: periodKey, department } }).then((r) => r.data),

  createObjective: (payload: { title: string; description?: string; department: string; period_key: string; owner_id?: number }) =>
    client.post<Objective>("/api/objectives", payload).then((r) => r.data),

  updateObjective: (id: number, payload: Partial<{ title: string; description: string; department: string; status: string; owner_id: number }>) =>
    client.patch<Objective>(`/api/objectives/${id}`, payload).then((r) => r.data),

  deleteObjective: (id: number) => client.delete(`/api/objectives/${id}`),

  createKeyResult: (
    objectiveId: number,
    payload: {
      title: string;
      measurement_type: "metric" | "milestone";
      weight?: number;
      unit?: string;
      baseline_value?: number;
      target_value?: number;
      current_value?: number;
      linked_kpi_key?: string;
      owner_id?: number;
    }
  ) => client.post<KeyResult>(`/api/objectives/${objectiveId}/key-results`, payload).then((r) => r.data),

  updateKeyResult: (
    objectiveId: number,
    krId: number,
    payload: Partial<{ title: string; weight: number; baseline_value: number; target_value: number; current_value: number; is_done: boolean; owner_id: number }>
  ) => client.patch<KeyResult>(`/api/objectives/${objectiveId}/key-results/${krId}`, payload).then((r) => r.data),

  deleteKeyResult: (objectiveId: number, krId: number) => client.delete(`/api/objectives/${objectiveId}/key-results/${krId}`),

  recordProgress: (objectiveId: number, krId: number, value: number, note?: string) =>
    client.post<KeyResult>(`/api/objectives/${objectiveId}/key-results/${krId}/progress`, { value, note }).then((r) => r.data),

  scoreboard: (periodKey: string) => client.get<OKRScoreboard>("/api/okrs/scoreboard", { params: { period_key: periodKey } }).then((r) => r.data),

  kpiOptions: () => client.get<string[]>("/api/okrs/kpi-options").then((r) => r.data),

  explain: (objectiveId: number, lang: "en" | "fa") =>
    client.post<ObjectiveExplanation>(`/api/objectives/${objectiveId}/explain`, undefined, { params: { lang } }).then((r) => r.data),
};
