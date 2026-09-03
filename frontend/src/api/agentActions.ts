import { client } from "./client";
import type { AgentActionLog } from "../types";

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const agentActionsApi = {
  list: (params?: { entity_type?: string; entity_id?: number; page?: number; page_size?: number }) =>
    client.get<Page<AgentActionLog>>("/api/agent-actions", { params }).then((r) => r.data),
  undo: (actionId: number) =>
    client.post<AgentActionLog>(`/api/agent-actions/${actionId}/undo`).then((r) => r.data),
};
