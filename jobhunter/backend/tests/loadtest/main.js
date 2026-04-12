import { SharedArray } from 'k6/data';
import { browse } from './scenario-browse.js';
import { onboard } from './scenario-onboard.js';
import { outreach } from './scenario-outreach.js';

export const options = {
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.10', abortOnFail: true, delayAbortEval: '30s' }],
    'http_req_duration{expected_response:true}': ['p(95)<5000'],
  },
  stages: [
    { duration: '2m', target: 10 },
    { duration: '5m', target: 100 },
    { duration: '5m', target: 300 },
    { duration: '5m', target: 700 },
    { duration: '5m', target: 1200 },
    { duration: '3m', target: 1200 },
    { duration: '30s', target: 0 },
  ],
};

const users = new SharedArray('users', () => JSON.parse(open('./fixtures/users.json')));

let onboardClaimed = 0;
export function tryClaimOnboardSlot(cap) {
  if (onboardClaimed >= cap) return false;
  onboardClaimed += 1;
  return true;
}

export default function () {
  const user = users[Math.floor(Math.random() * users.length)];
  const r = Math.random();
  if (r < 0.80) {
    browse(user);
  } else if (r < 0.95) {
    onboard(user, browse);
  } else {
    outreach(user);
  }
}
