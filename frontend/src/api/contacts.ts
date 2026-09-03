import { client } from "./client";
import type { Contact, ContactListItem, ContactPriority, ContactStatus, Page } from "../types";

export interface ContactInput {
  first_name: string;
  last_name?: string;
  email?: string | null;
  phone?: string | null;
  job_title?: string | null;
  status?: ContactStatus;
  priority?: ContactPriority;
  source?: string | null;
  notes?: string | null;
  company_id?: number | null;
  assigned_to_id?: number | null;
  tag_ids?: number[];
}

export const contactsApi = {
  list: (
    params: {
      search?: string;
      status?: ContactStatus;
      priority?: ContactPriority;
      tag_id?: number;
      company_id?: number;
      sort?: "priority";
      page?: number;
      page_size?: number;
    } = {}
  ) => client.get<Page<ContactListItem>>("/api/contacts", { params }).then((r) => r.data),
  get: (id: number) => client.get<Contact>(`/api/contacts/${id}`).then((r) => r.data),
  create: (data: ContactInput) => client.post<Contact>("/api/contacts", data).then((r) => r.data),
  update: (id: number, data: Partial<ContactInput>) =>
    client.patch<Contact>(`/api/contacts/${id}`, data).then((r) => r.data),
  remove: (id: number) => client.delete(`/api/contacts/${id}`),
};
