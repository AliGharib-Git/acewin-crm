import { client } from "./client";
import type { User, UserRole } from "../types";

export const usersApi = {
  list: () => client.get<User[]>("/api/users").then((r) => r.data),
  invite: (payload: { email: string; password: string; full_name: string; role: UserRole }) =>
    client.post<User>("/api/users", payload).then((r) => r.data),
  updateRole: (id: number, role: UserRole) =>
    client.patch<User>(`/api/users/${id}/role`, { role }).then((r) => r.data),
  toggleActive: (id: number) => client.patch<User>(`/api/users/${id}/deactivate`).then((r) => r.data),
  permissionsCatalog: () => client.get<Record<string, string[]>>("/api/users/permissions/catalog").then((r) => r.data),
  updatePermissions: (id: number, restricted_permissions: string[]) =>
    client.patch<User>(`/api/users/${id}/permissions`, { restricted_permissions }).then((r) => r.data),
};
