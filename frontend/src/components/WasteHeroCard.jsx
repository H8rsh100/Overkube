/**
 * WasteHeroCard — the big hero metric at the top of the dashboard.
 * Shows total recoverable $/month with an animated count-up,
 * plus service breakdown counts.
 */
import { useEffect, useRef, useState } from 'react'
import { fmtUSD } from '../lib/chartTheme'

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)
  const raf = useRef(null)

  useEffect(() => {
    if (target == null) return
    const start = performance.now()
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - t, 3)          // cubic ease-out
      setValue(target * ease)
      if (t < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return value
}

export default function WasteHeroCard({ report, loading }) {
  const savings = report?.total_monthly_savings ?? 0
  const animated = useCountUp(loading ? 0 : savings)

  const counts = report?.service_counts ?? {}

  if (loading) {
    return (
      <div className="rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] p-8">
        <div className="skeleton h-5 w-40 mb-4" />
        <div className="skeleton h-14 w-64 mb-3" />
        <div className="skeleton h-4 w-52" />
      </div>
    )
  }

  return (
    <div className="relative rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] p-8 overflow-hidden">
      {/* Subtle accent glow */}
      <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full bg-sky-400/5 blur-3xl pointer-events-none" />

      <p className="text-xs font-semibold tracking-widest uppercase text-[var(--color-subtle)] mb-3">
        Recoverable Spend
      </p>

      <div className="animate-countup">
        <span className="text-5xl font-bold tracking-tight text-[var(--color-text)]">
          {fmtUSD(animated)}
        </span>
        <span className="ml-2 text-lg text-[var(--color-subtle)]">/month</span>
      </div>

      <div className="mt-5 flex flex-wrap gap-4 text-sm">
        <Chip count={counts['over-provisioned'] ?? 0}  label="Over-provisioned"  color="text-orange-400" />
        <Chip count={counts['under-provisioned'] ?? 0} label="Under-provisioned" color="text-red-400" />
        <Chip count={counts['optimal'] ?? 0}           label="Optimal"           color="text-green-400" />
      </div>
    </div>
  )
}

function Chip({ count, label, color }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`text-2xl font-bold ${color}`}>{count}</span>
      <span className="text-[var(--color-subtle)]">{label}</span>
    </span>
  )
}
