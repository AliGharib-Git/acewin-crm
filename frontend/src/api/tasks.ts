import { client } from "./client";
import type { Page, Task, TaskPriority, TaskStatus, TaskType } from "../types";

export interface TaskInput {
  title: string;
  description?: string | null;
  due_date?: string | null;
  priority?: TaskPriority;
  status?: TaskStatus;
  task_type?: TaskType;
  reminder_minutes_before?: number | null;
  assigned_to_id?: number | null;
  contact_id?: number | null;
  deal_id?: number | null;
}

export const tasksApi = {
  list: (
    params: {
      status?: TaskStatus;
      task_type?: TaskType;
      assigned_to_id?: number;
      contact_id?: number;
      deal_id?: number;
      page?: number;
      page_size?: number;
    } = {}
  ) => client.get<Page<Task>>("/api/tasks", { params }).then((r) => r.data),
  get: (id: number) => client.get<Task>(`/api/tasks/${id}`).then((r) => r.data),
  create: (data: TaskInput) => client.post<Task>("/api/tasks", data).then((r) => r.data),
  update: (id: number, data: Partial<TaskInput>) =>
    client.patch<Task>(`/api/tasks/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/tasks/${id}`),
};
