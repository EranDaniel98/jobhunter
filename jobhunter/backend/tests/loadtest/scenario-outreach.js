import http from 'k6/http';
import { check } from 'k6';
import { login, authHeaders } from './lib/auth.js';

const BASE = __ENV.BASE_URL;

export function outreach(user) {
  const token = login(user.email, user.password);
  if (!token) return;
  const h = authHeaders(token);

  const companies = http.get(`${BASE}/api/v1/companies?limit=5`, { ...h, tags: { endpoint: 'companies_list' } });
  check(companies, { 'companies 200': (r) => r.status === 200 });
  const companyId = companies.json('items.0.id');
  if (!companyId) return;

  const dossier = http.get(`${BASE}/api/v1/companies/${companyId}/dossier`, { ...h, tags: { endpoint: 'dossier' } });
  check(dossier, { 'dossier 2xx': (r) => r.status >= 200 && r.status < 300 });

  const draft = http.post(
    `${BASE}/api/v1/outreach/draft`,
    JSON.stringify({ company_id: companyId }),
    { ...h, tags: { endpoint: 'outreach_draft' } },
  );
  check(draft, { 'draft 2xx': (r) => r.status >= 200 && r.status < 300 });

  http.get(`${BASE}/api/v1/analytics`, { ...h, tags: { endpoint: 'analytics' } });
}
