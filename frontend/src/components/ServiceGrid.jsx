/**
 * ServiceGrid — table of all services.
 * Each row shows: name, status pill, current vs recommended (mini bar),
 * monthly savings, confidence badge.
 * Click a row to expand the detail drawer (chart + recommendation).
 */
import { useState } from 'react'
import ConfidenceBadge from './ConfidenceBadge'
import ServiceDrawer from './ServiceDrawer'
import { fmtUSD, fmtCPU, fmtMem } from '../lib/chartTheme'

const STATUS_STYLES = {
  over:    { dot: 'bg-orange-400', text: 'text-orange-400', label: 'Over-provisioned' },
  under:   { dot: 'bg-red-400',    text: 'text-red-400',    label: 'Under-provisioned' },
  optimal: { dot: 'bg-green-400',  text: 'text-green-400',  label: 'Optimal' },
}

/** Mini bar showing current vs recommended as two horizontal bars */
function MiniBar({ current, recommended, unit = '' }) {
  if (current == null) return <span className="text-[var(--color-subtle)]">—</span>
  const max = Math.max(current, recommended ?? current, 1)
  const cPct = Math.round((current / max) * 100)
  const rPct = Math.round(((recommended ?? 0) / max) * 100)
  return (
    <div className="flex flex-col gap-1 min-w-[100px]">
      <div className="flex items-center gap-2 text-xs">
        <div className="flex-1 h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
          <div className="h-full rounded-full bg-orange-400 transition-all" style={{ width: `${cPct}%` }} />
        </div>
        <span className="text-[var(--color-subtle)] font-mono w-16 text-right">{fmtCPU(current)}</span>
      </div>
      {recommended != null && (
        <div className="flex items-center gap-2 text-xs">
          <div className="flex-1 h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
            <div className="h-full rounded-full bg-green-400 transition-all" style={{ width: `${rPct}%` }} />
          </div>
          <span className="text-green-400 font-mono w-16 text-right">{fmtCPU(recommended)}</span>
        </div>
      )}
    </div>
  )
}

function SkeletonRow() {
  return (
    <tr>
      {[140, 80, 120, 90, 80, 70].map((w, i) => (
        <td key={i} className="px-4 py-4">
          <div className={`skeleton h-4`} style={{ width: w }} />
        </td>
      ))}
    </tr>
  )
}

export default function ServiceGrid({ services, loading }) {
  const [selected, setSelected] = useState(null)

  return (
    <>
      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">Services</h2>
          <span className="text-xs text-[var(--color-subtle)]">Click a row to inspect</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[var(--color-subtle)] text-xs uppercase tracking-wider">
                <th className="px-4 py-3 text-left font-medium">Service</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">CPU req → rec</th>
                <th className="px-4 py-3 text-left font-medium">Mem req → rec</th>
                <th className="px-4 py-3 text-left font-medium">Savings/mo</th>
                <th className="px-4 py-3 text-left font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {loading
                ? Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
                : services.map((svc) => (
                    <ServiceRow
                      key={svc.service_name}
                      svc={svc}
                      selected={selected === svc.service_name}
                      onClick={() =>
                        setSelected((s) => s === svc.service_name ? null : svc.service_name)
                      }
                    />
                  ))
              }
            </tbody>
          </table>
        </div>
      </div>

      {/* Side drawer */}
      <ServiceDrawer
        serviceName={selected}
        onClose={() => setSelected(null)}
      />
    </>
  )
}

function ServiceRow({ svc, selected, onClick }) {
  const st = STATUS_STYLES[svc.waste_status] ?? STATUS_STYLES.optimal

  return (
    <tr
      onClick={onClick}
      className={`cursor-pointer transition-colors hover:bg-[var(--color-bg)]
        ${selected ? 'bg-[var(--color-bg)] ring-1 ring-inset ring-[var(--color-accent)]/30' : ''}`}
    >
      {/* Name */}
      <td className="px-4 py-4 font-mono text-[var(--color-text)] font-medium">
        {svc.service_name}
      </td>

      {/* Status */}
      <td className="px-4 py-4">
        <span className={`flex items-center gap-1.5 text-xs font-medium ${st.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
          {st.label}
        </span>
      </td>

      {/* CPU mini bar — placeholders; real data from recommendation in drawer */}
      <td className="px-4 py-4">
        <MiniBar current={svc.cpu_request} recommended={null} />
      </td>

      {/* Mem mini bar */}
      <td className="px-4 py-4">
        <span className="font-mono text-[var(--color-subtle)] text-xs">
          {fmtMem(svc.mem_request)}
        </span>
      </td>

      {/* Savings placeholder — filled via drawer rec data */}
      <td className="px-4 py-4 font-mono text-xs text-[var(--color-subtle)]">
        —
      </td>

      {/* Confidence — not in list payload; shown in drawer */}
      <td className="px-4 py-4">
        <ConfidenceBadge label="—" score="?" />
      </td>
    </tr>
  )
}
