import { client } from "./client";
import type { User, UserBrief } from "../types";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserBrief;
}

export const authApi = {
  login: (email: string, password: string) =>
    client.post<TokenResponse>("/api/auth/login", { email, password }).then((r) => r.data),

  register: (email: string, password: string, full_name: string, organization_name: string) =>
    client.post<TokenResponse>("/api/auth/register", { email, password, full_name, organization_name }).then((r) => r.data),

  me: () => client.get<User>("/api/auth/me").then((r) => r.data),
};
