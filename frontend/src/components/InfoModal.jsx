/**
 * InfoModal — "How this works" panel explaining the P90/P99 methodology
 * in plain language. Designed for demo / interview walkthroughs.
 * Triggered by clicking the (?) button in the top nav.
 */
export default function InfoModal({ open, onClose }) {
  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="pointer-events-auto w-full max-w-2xl rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl overflow-hidden">

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-[var(--color-border)]">
            <div className="flex items-center gap-3">
              <span className="text-[var(--color-accent)] text-xl">⚡</span>
              <h2 className="font-bold text-[var(--color-text)]">How Overkube Works</h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-[var(--color-subtle)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-6 space-y-5 overflow-y-auto max-h-[70vh] text-sm leading-relaxed">

            <Section title="The Problem">
              Kubernetes requires you to declare <code>requests</code> and <code>limits</code> for
              every container upfront — but most teams set these conservatively and never revisit them.
              The result: workloads that are 2–5× over-provisioned, paying for headroom that's never used.
            </Section>

            <Section title="What Overkube Does">
              <ol className="list-decimal list-inside space-y-2 text-[var(--color-subtle)]">
                <li><span className="text-[var(--color-text)]">Collects</span> real CPU and memory usage from your cluster every 30 seconds via the Kubernetes Metrics API.</li>
                <li><span className="text-[var(--color-text)]">Stores</span> up to 7 days of time-series data in a local SQLite database.</li>
                <li><span className="text-[var(--color-text)]">Computes</span> statistically-grounded recommendations using percentile analysis.</li>
                <li><span className="text-[var(--color-text)]">Quantifies</span> the waste in $/month using configurable cloud pricing rates.</li>
                <li><span className="text-[var(--color-text)]">Opens</span> a GitHub Pull Request patching the manifest — so a human reviews and merges it.</li>
              </ol>
            </Section>

            <Section title="The P90 / P99 Method">
              <p className="text-[var(--color-subtle)] mb-3">
                Instead of guessing, we let actual behaviour define the right size:
              </p>
              <div className="rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[var(--color-subtle)] uppercase tracking-wider border-b border-[var(--color-border)]">
                      <th className="px-4 py-2 text-left">Field</th>
                      <th className="px-4 py-2 text-left">Formula</th>
                      <th className="px-4 py-2 text-left">Why</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    <tr>
                      <td className="px-4 py-2 font-mono text-[var(--color-text)]">CPU Request</td>
                      <td className="px-4 py-2 text-[var(--color-accent)]">P90 of usage</td>
                      <td className="px-4 py-2 text-[var(--color-subtle)]">Handles 90% of real load; Kubernetes schedules pods based on this.</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-mono text-[var(--color-text)]">CPU Limit</td>
                      <td className="px-4 py-2 text-[var(--color-accent)]">max(P99, 1.2× request)</td>
                      <td className="px-4 py-2 text-[var(--color-subtle)]">Caps bursts. CPU throttling is recoverable — unlike OOM kills.</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-mono text-[var(--color-text)]">Memory Request</td>
                      <td className="px-4 py-2 text-[var(--color-accent)]">P90 of usage</td>
                      <td className="px-4 py-2 text-[var(--color-subtle)]">Memory is non-compressible; Kubernetes evicts pods that exceed this.</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-mono text-[var(--color-text)]">Memory Limit</td>
                      <td className="px-4 py-2 text-[var(--color-accent)]">P99 + 32 MiB buffer</td>
                      <td className="px-4 py-2 text-[var(--color-subtle)]">OOMs kill pods instantly — we bias conservative on memory.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Section>

            <Section title="Confidence Score">
              Each recommendation comes with a <strong className="text-[var(--color-text)]">confidence score (0–100)</strong> based on:
              <ul className="mt-2 space-y-1 text-[var(--color-subtle)]">
                <li>🟢 <strong className="text-[var(--color-text)]">Sample count (30%)</strong> — more data = more confidence</li>
                <li>🟡 <strong className="text-[var(--color-text)]">Predictability (50%)</strong> — low coefficient of variation = stable usage = better P90 accuracy</li>
                <li>🔵 <strong className="text-[var(--color-text)]">Recency (20%)</strong> — stale data degrades confidence linearly over 7 days</li>
              </ul>
            </Section>

            <Section title="vs Kubernetes VPA / Goldilocks / Kubecost">
              <div className="rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[var(--color-subtle)] uppercase tracking-wider border-b border-[var(--color-border)]">
                      <th className="px-4 py-2 text-left">Feature</th>
                      <th className="px-4 py-2 text-center">VPA</th>
                      <th className="px-4 py-2 text-center">Kubecost</th>
                      <th className="px-4 py-2 text-center text-[var(--color-accent)]">Overkube</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {[
                      ['Recommendations', '✅', '✅', '✅'],
                      ['Confidence scoring', '❌', '❌', '✅'],
                      ['$ waste quantification', '❌', '✅', '✅'],
                      ['Auto-PR to fix it', '❌', '❌', '✅'],
                      ['Human-reviewable (no silent restarts)', '⚠️', '✅', '✅'],
                    ].map(([feat, vpa, kc, ok]) => (
                      <tr key={feat}>
                        <td className="px-4 py-2 text-[var(--color-subtle)]">{feat}</td>
                        <td className="px-4 py-2 text-center">{vpa}</td>
                        <td className="px-4 py-2 text-center">{kc}</td>
                        <td className="px-4 py-2 text-center text-[var(--color-accent)] font-semibold">{ok}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

          </div>
        </div>
      </div>
    </>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <h3 className="font-semibold text-[var(--color-text)] mb-2">{title}</h3>
      <div className="text-[var(--color-subtle)]">{children}</div>
    </div>
  )
}
