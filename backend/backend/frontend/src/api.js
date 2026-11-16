/**
 * api.js – Ingredia frontend API wrapper.
 *
 * All endpoints live under /api/v1.
 * Base URL from: VITE_API_URL in .env (defaults to http://localhost:8000).
 *
 * Never add mock/fallback data. If the server returns an error, throw it.
 */

const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') + '/api/v1';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch (_) { /* ignore */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// ─── Products ────────────────────────────────────────────────────────────────

/** GET /api/v1/products?skip=&limit= */
export async function listProducts({ skip = 0, limit = 50 } = {}) {
  return request(`/products?skip=${skip}&limit=${limit}`);
}

/** GET /api/v1/products/search?query= */
export async function searchProducts(query) {
  return request(`/products/search?query=${encodeURIComponent(query)}`);
}

/** GET /api/v1/products/:id  – includes product_ingredients[].ingredient */
export async function getProduct(id) {
  return request(`/products/${id}`);
}

/** GET /api/v1/products/:id/risk */
export async function getRiskAnalysis(id) {
  return request(`/products/${id}/risk`);
}

/** GET /api/v1/scans/:id/analysis */
export async function getScanAnalysis(id) {
  return request(`/scans/${id}/analysis`);
}

// ─── Ingredients ─────────────────────────────────────────────────────────────

/** GET /api/v1/ingredients/search?query= */
export async function searchIngredients(query) {
  return request(`/ingredients/search?query=${encodeURIComponent(query)}`);
}

/** GET /api/v1/ingredients/:id */
export async function getIngredient(id) {
  return request(`/ingredients/${id}`);
}

// ─── Scans ───────────────────────────────────────────────────────────────────

/**
 * POST /api/v1/scans/upload  (multipart, field: "file")
 * Returns full ScanRead with scan_ingredients.
 */
export async function uploadScan(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/scans/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch (_) { /* ignore */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

/**
 * POST /api/v1/scans/text  { text: string }
 * Returns full ScanRead.
 */
export async function submitScanText(text) {
  return request('/scans/text', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

/** GET /api/v1/scans?skip=&limit= */
export async function listScans({ skip = 0, limit = 50 } = {}) {
  return request(`/scans?skip=${skip}&limit=${limit}`);
}

/** GET /api/v1/scans/:id */
export async function getScanReview(id) {
  return request(`/scans/${id}`);
}

/**
 * PATCH /api/v1/scans/:scanId/ingredients/:siId
 * body: { user_accepted: boolean }
 * Returns updated ScanRead.
 */
export async function patchScanIngredient(scanId, siId, userAccepted) {
  return request(`/scans/${scanId}/ingredients/${siId}`, {
    method: 'PATCH',
    body: JSON.stringify({ user_accepted: userAccepted }),
  });
}

/**
 * POST /api/v1/scans/:id/confirm
 * Returns updated ScanRead with status "user_confirmed".
 */
export async function confirmScan(id) {
  return request(`/scans/${id}/confirm`, { method: 'POST' });
}
