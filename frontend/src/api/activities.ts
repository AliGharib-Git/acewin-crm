import { client } from "./client";
import type { Activity, ActivityType } from "../types";

export const activitiesApi = {
  list: (params: { contact_id?: number; deal_id?: number }) =>
    client.get<Activity[]>("/api/activities", { params }).then((r) => r.data),
  create: (data: { type: ActivityType; content: string; contact_id?: number; deal_id?: number }) =>
    client.post<Activity>("/api/activities", data).then((r) => r.data),
};
