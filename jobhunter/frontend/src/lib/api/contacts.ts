import api from "./client";
import type { ContactResponse } from "../types";

export async function findContact(
  company_id: string,
  first_name: string,
  last_name: string
): Promise<ContactResponse> {
  const { data } = await api.post<ContactResponse>("/contacts/find", {
    company_id,
    first_name,
    last_name,
  });
  return data;
}

export async function verifyContact(contactId: string): Promise<ContactResponse> {
  const { data } = await api.post<ContactResponse>(`/contacts/${contactId}/verify`);
  return data;
}
