import { client } from "./client";
import type { CopilotAnswer } from "../types";

export const copilotApi = {
  ask: (query: string, lang: "en" | "fa") => client.post<CopilotAnswer>("/api/copilot/ask", { query, lang }).then((r) => r.data),
};
