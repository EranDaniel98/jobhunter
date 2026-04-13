import http from 'k6/http';
import { sleep, check } from 'k6';
import { Counter } from 'k6/metrics';
import { login, authHeaders } from './lib/auth.js';
import { tryClaimOnboardSlot } from './main.js';

const BASE = __ENV.BASE_URL;
const ONBOARD_CAP = parseInt(__ENV.ONBOARD_CAP || '200', 10);
const RESUME_PDF = open('./fixtures/sample-resume.pdf', 'b');

export const onboardStarted = new Counter('loadtest_onboard_started');
export const onboardSkipped = new Counter('loadtest_onboard_skipped_cap');

export function onboard(user, runBrowseFallback) {
  if (!tryClaimOnboardSlot(ONBOARD_CAP)) {
    onboardSkipped.add(1);
    runBrowseFallback(user);
    return;
  }
  onboardStarted.add(1);

  const email = `onboard-${__VU}-${__ITER}-${Date.now()}@loadtest.local`;
  const reg = http.post(
    `${BASE}/api/v1/auth/register`,
    JSON.stringify({ email, password: 'LoadTest!1' }),
    { headers: { 'Content-Type': 'application/json' }, tags: { endpoint: 'register' } },
  );
  check(reg, { 'register 201': (r) => r.status === 201 });
  if (reg.status !== 201) return;

  const token = reg.json('access_token') || login(email, 'LoadTest!1');
  const h = authHeaders(token);

  const upload = http.post(
    `${BASE}/api/v1/resume/upload`,
    { file: http.file(RESUME_PDF, 'resume.pdf', 'application/pdf') },
    { headers: { Authorization: `Bearer ${token}` }, tags: { endpoint: 'resume_upload' } },
  );
  check(upload, { 'upload 2xx': (r) => r.status >= 200 && r.status < 300 });

  for (let i = 0; i < 30; i++) {
    sleep(2);
    const r = http.get(`${BASE}/api/v1/resume`, { ...h, tags: { endpoint: 'resume_poll' } });
    const status = r.json('status');
    if (status === 'complete' || status === 'failed' || status === 'skipped') break;
  }

  http.get(`${BASE}/api/v1/dashboard`, { ...h, tags: { endpoint: 'dashboard' } });
}
