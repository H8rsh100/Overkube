/**
 * Overkube API client
 * Thin fetch wrapper — all functions return parsed JSON or throw on error.
 * Base URL is set via VITE_API_BASE_URL env var (defaults to http://localhost:8000).
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

/** GET /services — list all monitored services */
export const getServices = () => request('/services')

/** GET /services/{name}/recommendation */
export const getRecommendation = (name, days = 7) =>
  request(`/services/${encodeURIComponent(name)}/recommendation?days=${days}`)

/** GET /services/{name}/history */
export const getHistory = (name, days = 7) =>
  request(`/services/${encodeURIComponent(name)}/history?days=${days}`)

/** GET /waste-report */
export const getWasteReport = () => request('/waste-report')

/** POST /services/{name}/recommendation/apply */
export const applyRecommendation = (name, reason = '') =>
  request(`/services/${encodeURIComponent(name)}/recommendation/apply`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
