/**
 * ServiceDrawer — slide-in panel that shows full recommendation details
 * and the usage chart when a service row is selected.
 */
import { useEffect, useState } from 'react'
import { getRecommendation, getHistory, applyRecommendation } from '../api/client'
import UsageChart from './UsageChart'
import ConfidenceBadge from './ConfidenceBadge'
import { fmtUSD, fmtCPU, fmtMem } from '../lib/chartTheme'

export default function ServiceDrawer({ serviceName, onClose }) {
  const [rec, setRec]         = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode]       = useState('cpu')   // 'cpu' | 'mem'
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState(null)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!serviceName) { setRec(null); setHistory(null); setApplyResult(null); return }
    setLoading(true)
    setError(null)
    setApplyResult(null)
    Promise.all([
      getRecommendation(serviceName),
      getHistory(serviceName, 7),
    ])
      .then(([r, h]) => { setRec(r); setHistory(h) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [serviceName])

  const handleApply = async () => {
    setApplying(true)
    try {
      const res = await applyRecommendation(serviceName, 'Applied from dashboard')
      setApplyResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setApplying(false)
    }
  }

  const open = !!serviceName

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <aside
        className={`fixed top-0 right-0 h-full w-full max-w-2xl z-50 flex flex-col
          bg-[var(--color-surface)] border-l border-[var(--color-border)]
          shadow-2xl transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-[var(--color-border)]">
          <div>
            <p className="text-xs text-[var(--color-subtle)] uppercase tracking-widest mb-0.5">Service</p>
            <h2 className="font-mono font-semibold text-[var(--color-text)]">{serviceName}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-[var(--color-subtle)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            aria-label="Close drawer"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Chart mode toggle */}
          <div className="flex gap-2">
            {['cpu', 'mem'].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                  ${mode === m
                    ? 'bg-[var(--color-accent)] text-[var(--color-bg)]'
                    : 'bg-[var(--color-bg)] text-[var(--color-subtle)] hover:text-[var(--color-text)]'
                  }`}
              >
                {m.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Chart */}
          <UsageChart history={history} recommendation={rec} mode={mode} loading={loading} />

          {/* Recommendation card */}
          {loading ? (
            <div className="space-y-3">
              {[200, 160, 180].map((w, i) => (
                <div key={i} className="skeleton h-4" style={{ width: w }} />
              ))}
            </div>
          ) : rec ? (
            <RecDetail rec={rec} />
          ) : null}

          {/* Apply button */}
          {rec && !applyResult && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="w-full py-3 rounded-xl bg-[var(--color-accent)] text-[var(--color-bg)]
                font-semibold text-sm hover:brightness-110 active:scale-[0.98]
                disabled:opacity-50 transition-all"
            >
              {applying ? 'Applying…' : 'Apply Recommendation'}
            </button>
          )}

          {/* Apply result toast */}
          {applyResult && (
            <div className="rounded-xl bg-green-500/10 border border-green-500/30 px-5 py-4 text-sm">
              <p className="font-semibold text-green-400 mb-1">Recommendation applied ✓</p>
              <p className="text-[var(--color-subtle)]">{applyResult.message}</p>
              {applyResult.pull_request_url && (
                <a
                  href={applyResult.pull_request_url}
                  target="_blank" rel="noreferrer"
                  className="mt-2 inline-block text-[var(--color-accent)] hover:underline"
                >
                  View PR →
                </a>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

/** Recommendation detail panel — resource table + confidence + reasoning */
function RecDetail({ rec }) {
  const { current: cur, recommended: reco, confidence, savings, reasoning, status } = rec

  const statusColor = {
    'over-provisioned':  'text-orange-400',
    'under-provisioned': 'text-red-400',
    'optimal':           'text-green-400',
  }[status] ?? 'text-[var(--color-subtle)]'

  return (
    <div className="space-y-5">
      {/* Status + confidence row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`text-sm font-semibold capitalize ${statusColor}`}>{status}</span>
        <ConfidenceBadge label={confidence.label} score={confidence.score} />
        {savings.monthly_savings > 0 && (
          <span className="ml-auto text-sm font-mono text-green-400 font-semibold">
            {fmtUSD(savings.monthly_savings)}/mo savings
          </span>
        )}
      </div>

      {/* Resource comparison table */}
      <div className="rounded-xl border border-[var(--color-border)] overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[var(--color-bg)] text-[var(--color-subtle)] uppercase tracking-wider">
              <th className="px-4 py-2 text-left font-medium">Resource</th>
              <th className="px-4 py-2 text-right font-medium">Current</th>
              <th className="px-4 py-2 text-right font-medium">Recommended</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            <ResourceRow label="CPU request"    curr={fmtCPU(cur.cpu_request)}    rec={fmtCPU(reco.cpu_request)}    better={reco.cpu_request < cur.cpu_request} />
            <ResourceRow label="CPU limit"      curr={fmtCPU(cur.cpu_limit)}      rec={fmtCPU(reco.cpu_limit)}      better={reco.cpu_limit < cur.cpu_limit} />
            <ResourceRow label="Memory request" curr={fmtMem(cur.mem_request)}    rec={fmtMem(reco.mem_request)}    better={reco.mem_request < cur.mem_request} />
            <ResourceRow label="Memory limit"   curr={fmtMem(cur.mem_limit)}      rec={fmtMem(reco.mem_limit)}      better={reco.mem_limit < cur.mem_limit} />
            <tr className="bg-[var(--color-bg)]">
              <td className="px-4 py-2 text-[var(--color-subtle)]">Cost/month</td>
              <td className="px-4 py-2 text-right font-mono text-[var(--color-text)]">{fmtUSD(cur.monthly_cost)}</td>
              <td className="px-4 py-2 text-right font-mono text-green-400 font-semibold">{fmtUSD(reco.monthly_cost)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Reasoning */}
      <div className="text-xs text-[var(--color-subtle)] leading-relaxed bg-[var(--color-bg)] rounded-xl px-4 py-3 border border-[var(--color-border)]">
        <p className="font-semibold text-[var(--color-text)] mb-1">Why?</p>
        {reasoning}
      </div>

      {/* Sample count */}
      <p className="text-xs text-[var(--color-subtle)]">
        Based on <span className="text-[var(--color-text)] font-medium">{rec.sample_count.toLocaleString()}</span> samples
        over the last {rec.lookback_days} days.
      </p>
    </div>
  )
}

function ResourceRow({ label, curr, rec, better }) {
  return (
    <tr>
      <td className="px-4 py-2 text-[var(--color-subtle)]">{label}</td>
      <td className="px-4 py-2 text-right font-mono text-[var(--color-text)]">{curr}</td>
      <td className={`px-4 py-2 text-right font-mono font-semibold ${better ? 'text-green-400' : 'text-red-400'}`}>
        {rec}
      </td>
    </tr>
  )
}
