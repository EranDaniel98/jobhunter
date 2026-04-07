import http from 'k6/http';
import { sleep, check } from 'k6';
import { login, authHeaders } from './lib/auth.js';

const BASE = __ENV.BASE_URL;

export function browse(user) {
  const token = login(user.email, user.password);
  if (!token) return;
  const h = authHeaders(token);

  const dash = http.get(`${BASE}/api/v1/dashboard`, { ...h, tags: { endpoint: 'dashboard' } });
  check(dash, { 'dashboard 200': (r) => r.status === 200 });

  const jobs = http.get(`${BASE}/api/v1/jobs?limit=20`, { ...h, tags: { endpoint: 'jobs_list' } });
  check(jobs, { 'jobs 200': (r) => r.status === 200 });

  const first = jobs.json('items.0.id');
  if (first) {
    const one = http.get(`${BASE}/api/v1/jobs/${first}`, { ...h, tags: { endpoint: 'job_detail' } });
    check(one, { 'job 200': (r) => r.status === 200 });
  }

  const resume = http.get(`${BASE}/api/v1/resume`, { ...h, tags: { endpoint: 'resume_get' } });
  check(resume, { 'resume 200 or 404': (r) => r.status === 200 || r.status === 404 });

  sleep(2 + Math.random() * 3);
}
