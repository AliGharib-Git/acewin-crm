import { client } from "./client";
import type { PipelineStage } from "../types";

export interface StageInput {
  name: string;
  order?: number;
  color?: string;
  is_won?: boolean;
  is_lost?: boolean;
}

export const pipelineApi = {
  list: () => client.get<PipelineStage[]>("/api/pipeline-stages").then((r) => r.data),
  create: (data: StageInput) => client.post<PipelineStage>("/api/pipeline-stages", data).then((r) => r.data),
  update: (id: number, data: Partial<StageInput>) =>
    client.patch<PipelineStage>(`/api/pipeline-stages/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/pipeline-stages/${id}`),
};
