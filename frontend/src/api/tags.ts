import { client } from "./client";
import type { Tag } from "../types";

export const tagsApi = {
  list: () => client.get<Tag[]>("/api/tags").then((r) => r.data),
  create: (name: string, color: string) => client.post<Tag>("/api/tags", { name, color }).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/tags/${id}`),
};
