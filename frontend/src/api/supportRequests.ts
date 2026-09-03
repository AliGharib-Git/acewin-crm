import { client } from "./client";
import type { SupportRequest } from "../types";

export const supportRequestsApi = {
  list: () => client.get<SupportRequest[]>("/api/support-requests").then((r) => r.data),

  create: (payload: { subject: string; message: string }) =>
    client.post<SupportRequest>("/api/support-requests", payload).then((r) => r.data),
};
