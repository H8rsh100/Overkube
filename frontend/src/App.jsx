/**
 * App.jsx — main layout
 * Dark HUD dashboard: top nav + hero card + service grid.
 * All data is fetched here and passed down; errors are handled
 * intentionally at the top level.
 */
import { useEffect, useState, useCallback } from 'react'
import { getServices, getWasteReport } from './api/client'
import WasteHeroCard from './components/WasteHeroCard'
import ServiceGrid    from './components/ServiceGrid'
import InfoModal      from './components/InfoModal'

function useInterval(cb, ms) {
  useEffect(() => {
    const id = setInterval(cb, ms)
    return () => clearInterval(id)
  }, [cb, ms])
}

export default function App() {
  const [services, setServices]   = useState([])
  const [report, setReport]       = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [showInfo, setShowInfo]   = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [svcs, rep] = await Promise.all([getServices(), getWasteReport()])
      setServices(svcs)
      setReport(rep)
      setLastUpdated(new Date())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useInterval(fetchAll, 30_000)   // auto-refresh every 30 s

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">

      {/* ── Top Nav ─────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[var(--color-bg)]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <span className="text-[var(--color-accent)] text-lg">⚡</span>
            <span className="font-bold tracking-tight">Overkube</span>
            <span className="hidden sm:inline text-xs text-[var(--color-subtle)] bg-[var(--color-surface)] border border-[var(--color-border)] px-2 py-0.5 rounded-full">
              kind-overkube
            </span>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-4 text-xs text-[var(--color-subtle)]">
            {lastUpdated && (
              <span>
                Updated{' '}
                <time dateTime={lastUpdated.toISOString()}>
                  {lastUpdated.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                </time>
              </span>
            )}
            <button
              onClick={() => setShowInfo(true)}
              className="px-2.5 py-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-accent)] font-medium hover:bg-[var(--color-muted)] transition-colors"
            >
              How it works
            </button>
            <button
              onClick={fetchAll}
              className="p-1.5 rounded-lg hover:bg-[var(--color-surface)] transition-colors"
              aria-label="Refresh data"
              title="Refresh"
            >
              ↻
            </button>
          </div>
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">

        {/* Error banner */}
        {error && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-5 py-4 text-sm">
            <p className="font-semibold text-red-400 mb-1">Could not reach the backend</p>
            <p className="text-[var(--color-subtle)]">{error}</p>
            <p className="mt-2 text-[var(--color-subtle)]">
              Make sure the API is running:{' '}
              <code className="font-mono text-[var(--color-accent)]">
                uvicorn app.main:app --reload --port 8000
              </code>
            </p>
          </div>
        )}

        {/* Hero */}
        <WasteHeroCard report={report} loading={loading} />

        {/* Service grid */}
        <ServiceGrid services={services} loading={loading} />

        {/* Footer */}
        <footer className="text-center text-xs text-[var(--color-subtle)] pb-4">
          Overkube · Kubernetes FinOps Engine ·{' '}
          <a
            href="https://github.com/H8rsh100/Overkube"
            target="_blank" rel="noreferrer"
            className="text-[var(--color-accent)] hover:underline"
          >
            GitHub
          </a>
        </footer>
      </main>

      {/* Info Modal */}
      <InfoModal open={showInfo} onClose={() => setShowInfo(false)} />
    </div>
  )
}
