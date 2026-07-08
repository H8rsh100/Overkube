/**
 * Recharts theme config — single source of truth for all chart colours/styles.
 * Import this in any component that renders a Recharts chart.
 */

export const CHART = {
  // Line / area colours
  usage:     '#38bdf8',   // sky-400  — actual usage
  request:   '#f97316',   // orange   — current request (dashed)
  limit:     '#6b7280',   // gray-500 — current limit (dotted)
  rec:       '#22c55e',   // green    — recommended band
  recFill:   '#22c55e22', // green 13% opacity — shaded area

  // Grid / axis
  grid:      '#1f2937',
  axis:      '#4b5563',
  tick:      '#9ca3af',
  tooltip:   '#111827',
  tooltipBorder: '#1f2937',

  // Dimensions
  strokeWidth: 2,
  dotRadius:   3,
  activeDot:   5,
}

/** Format epoch seconds → human-readable date string for axis ticks */
export function fmtTime(epoch) {
  const d = new Date(epoch * 1000)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** Format epoch seconds → full tooltip timestamp */
export function fmtTimestamp(epoch) {
  return new Date(epoch * 1000).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** Format millicores → human string  e.g. 1250 → "1.25 vCPU" */
export function fmtCPU(m) {
  if (m == null) return '—'
  return m >= 1000 ? `${(m / 1000).toFixed(2)} vCPU` : `${m}m`
}

/** Format MiB → human string  e.g. 1024 → "1.00 GiB" */
export function fmtMem(mib) {
  if (mib == null) return '—'
  return mib >= 1024 ? `${(mib / 1024).toFixed(2)} GiB` : `${Math.round(mib)} MiB`
}

/** Format dollars */
export function fmtUSD(n) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', minimumFractionDigits: 2,
  }).format(n ?? 0)
}
