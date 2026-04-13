import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL;

export function login(email, password) {
  const res = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({ email, password }), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'login' },
  });
  check(res, { 'login 200': (r) => r.status === 200 });
  return res.json('access_token');
}

export function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };
}
