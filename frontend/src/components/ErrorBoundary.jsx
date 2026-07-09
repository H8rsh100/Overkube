/**
 * ErrorBoundary — catches render errors anywhere in the subtree.
 * Shows a styled fallback instead of a blank page.
 */
import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[Overkube ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center p-8">
        <div className="max-w-lg w-full rounded-2xl bg-[var(--color-surface)] border border-red-500/30 p-8 space-y-4">
          <div className="text-4xl">⚠️</div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Something went wrong</h1>
          <p className="text-sm text-[var(--color-subtle)] leading-relaxed">
            An unexpected error occurred in the dashboard. This is likely a frontend issue.
          </p>
          <details className="text-xs font-mono text-red-400 bg-[var(--color-bg)] rounded-lg p-3 max-h-40 overflow-auto">
            <summary className="cursor-pointer mb-2 text-[var(--color-subtle)]">Error details</summary>
            {this.state.error?.toString()}
          </details>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-[var(--color-bg)] text-sm font-semibold hover:brightness-110 transition-all"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }
}
