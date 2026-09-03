import { client } from "./client";
import type { PublicFeedback, PublicFeedbackCategory } from "../types";

export const feedbackApi = {
  submit: (payload: { name: string; email?: string | null; category: PublicFeedbackCategory; message: string }) =>
    client.post<PublicFeedback>("/api/feedback", payload).then((r) => r.data),
};
