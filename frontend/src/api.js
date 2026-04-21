const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

// ---------------------------------------------------------------------------
// Password — stored in sessionStorage after user enters it on the gate screen
// ---------------------------------------------------------------------------
export function getPassword() {
  return sessionStorage.getItem('app_password') || '';
}
export function setPassword(pw) {
  sessionStorage.setItem('app_password', pw);
}

// ---------------------------------------------------------------------------
// Client-side cache — avoids repeat fetches when switching tabs back/forth.
// GET requests are cached for 2 minutes. POST (chat) is never cached.
// ---------------------------------------------------------------------------
const _cache = new Map();
const CACHE_TTL = 2 * 60 * 1000; // 2 minutes in ms

function authHeaders() {
  const pw = getPassword();
  return pw ? { 'X-App-Password': pw } : {};
}

async function cachedGet(url) {
  const now = Date.now();
  const hit = _cache.get(url);
  if (hit && now - hit.ts < CACHE_TTL) return hit.data;

  const res = await fetch(url, { headers: authHeaders() });
  if (res.status === 401) throw new Error('UNAUTHORIZED');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  _cache.set(url, { data, ts: now });
  return data;
}

/** Invalidate all cached entries whose URL contains the given substring. */
export function invalidateCache(substring = '') {
  for (const key of _cache.keys()) {
    if (!substring || key.includes(substring)) _cache.delete(key);
  }
}

// ---------------------------------------------------------------------------

function buildParams(filters) {
  const params = new URLSearchParams();
  if (filters.startDate) params.append('start_date', filters.startDate);
  if (filters.endDate) params.append('end_date', filters.endDate);
  if (filters.status) params.append('status', filters.status);
  if (filters.region) params.append('region', filters.region);
  if (filters.account) params.append('account', filters.account);
  if (filters.selectedCampaigns && filters.selectedCampaigns.length > 0) {
    params.append('campaigns', filters.selectedCampaigns.join(','));
  }
  return params.toString();
}

export async function fetchCampaigns(filters) {
  return cachedGet(`${BASE_URL}/api/campaigns?${buildParams(filters)}`);
}

export async function fetchKeywords(filters) {
  return cachedGet(`${BASE_URL}/api/keywords?${buildParams(filters)}`);
}

export async function fetchSearchTerms(filters) {
  return cachedGet(`${BASE_URL}/api/search-terms?${buildParams(filters)}`);
}

export async function fetchComparison(periods = 12, startDate = null, endDate = null, account = 'india') {
  const params = new URLSearchParams();
  params.append('periods', periods);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  params.append('account', account);
  return cachedGet(`${BASE_URL}/api/comparison?${params.toString()}`);
}

export async function fetchKeywordIdeas(filters) {
  return cachedGet(`${BASE_URL}/api/keyword-ideas?${buildParams(filters)}`);
}

export async function fetchCompetitorKeywords(domain, region = 'All') {
  const params = new URLSearchParams();
  params.append('domain', domain);
  if (region) params.append('region', region);
  return cachedGet(`${BASE_URL}/api/competitor-keywords?${params.toString()}`);
}

export async function fetchAuctionInsights(filters) {
  return cachedGet(`${BASE_URL}/api/auction-insights?${buildParams(filters)}`);
}

export async function sendChatMessage(message, history, context, account = 'india') {
  // Chat is never cached — always fresh
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, history, context, account }),
  });
  if (res.status === 401) throw new Error('UNAUTHORIZED');
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json();
}
