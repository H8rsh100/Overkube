/**
 * ConfidenceBadge — colour-coded pill showing confidence level.
 * Props: label ("high"|"medium"|"low"), score (0-100)
 */
export default function ConfidenceBadge({ label, score }) {
  const styles = {
    high:   'bg-green-500/15 text-green-400  ring-green-500/30',
    medium: 'bg-amber-500/15 text-amber-400  ring-amber-500/30',
    low:    'bg-gray-500/15  text-gray-400   ring-gray-500/30',
  }
  const cls = styles[label] ?? styles.low

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ${cls}`}
      title={`Confidence score: ${score}/100`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {label ?? 'low'}
      <span className="opacity-60">{score}</span>
    </span>
  )
}
