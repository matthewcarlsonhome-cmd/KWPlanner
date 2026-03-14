/**
 * API client for the MCC Keyword Research Platform backend.
 */

const BASE_URL = '/api';

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }

  // Handle binary responses (CSV, Excel)
  const contentType = response.headers.get('content-type');
  if (contentType && (contentType.includes('text/csv') || contentType.includes('spreadsheet'))) {
    return response.blob();
  }

  return response.json();
}

// --- Auth ---
export const auth = {
  me: () => request('/auth/me'),
  logout: () => request('/auth/logout', { method: 'POST' }),
};

// --- Accounts ---
export const accounts = {
  list: () => request('/accounts'),
  get: (id) => request(`/accounts/${id}`),
  sync: () => request('/accounts/sync', { method: 'POST' }),
};

// --- Research ---
export const research = {
  run: (accountId) => request('/research/run', {
    method: 'POST',
    body: JSON.stringify(accountId ? { account_id: accountId } : {}),
  }),
  status: () => request('/research/status'),
  listRuns: (accountId) => request(`/research/runs${accountId ? `?account_id=${accountId}` : ''}`),
  getRun: (runId) => request(`/research/runs/${runId}`),
};

// --- Results ---
export const results = {
  get: (accountId, params = {}) => {
    const query = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null && val !== '') query.set(key, val);
    }
    const qs = query.toString();
    return request(`/results/${accountId}${qs ? `?${qs}` : ''}`);
  },
  seeds: (accountId) => request(`/results/${accountId}/seeds`),
  negatives: (accountId) => request(`/results/${accountId}/negatives`),
  compare: (accountId, runA, runB) =>
    request(`/results/${accountId}/compare?run_a=${runA}&run_b=${runB}`),
};

// --- Decisions ---
export const decisions = {
  create: (data) => request('/decisions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  update: (id, data) => request(`/decisions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  get: (accountId, status) =>
    request(`/decisions/${accountId}${status ? `?status=${status}` : ''}`),
};

// --- Export ---
export const exportApi = {
  googleAdsEditor: (data) => request('/export/google-ads-editor', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  negatives: (accountId) => request(`/export/negatives?account_id=${accountId}`, {
    method: 'POST',
  }),
  allAccounts: (data) => request('/export/all-accounts', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

// --- Settings ---
export const settings = {
  get: () => request('/settings'),
  update: (data) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
};

// Helper: trigger file download from blob
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
