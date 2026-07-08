/**
 * UsageChart — time-series Recharts chart per service.
 * Shows: actual usage (solid line) vs current request (dashed) vs
 * recommended band (shaded area + solid line).
 */
import {
  ResponsiveContainer, ComposedChart, Area, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { CHART, fmtTime, fmtTimestamp, fmtCPU, fmtMem } from '../lib/chartTheme'

function CustomTooltip({ active, payload, label, mode }) {
  if (!active || !payload?.length) return null
  const fmt = mode === 'cpu' ? fmtCPU : fmtMem
  return (
    <div
      style={{ background: CHART.tooltip, border: `1px solid ${CHART.tooltipBorder}` }}
      className="rounded-lg p-3 text-xs shadow-xl min-w-[180px]"
    >
      <p className="text-[var(--color-subtle)] mb-2">{fmtTimestamp(label)}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-4 mb-1">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-mono font-medium text-[var(--color-text)]">
            {fmt(p.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function UsageChart({ history, recommendation, mode = 'cpu', loading }) {
  if (loading) {
    return <div className="skeleton w-full h-64 rounded-xl" />
  }

  if (!history?.points?.length) {
    return (
      <div className="flex items-center justify-center h-64 rounded-xl border border-dashed border-[var(--color-border)] text-[var(--color-subtle)] text-sm">
        No history data available yet.
      </div>
    )
  }

  const rec = recommendation
  const recReq  = mode === 'cpu' ? rec?.recommended?.cpu_request  : rec?.recommended?.mem_request
  const currReq = mode === 'cpu' ? rec?.current?.cpu_request      : rec?.current?.mem_request
  const currLim = mode === 'cpu' ? rec?.current?.cpu_limit        : rec?.current?.mem_limit

  const data = history.points.map((p) => ({
    ts:      p.timestamp,
    usage:   mode === 'cpu' ? p.cpu_usage_millicores : p.mem_usage_mb,
    request: mode === 'cpu' ? p.cpu_request          : p.mem_request,
    limit:   mode === 'cpu' ? p.cpu_limit            : p.mem_limit,
  }))

  const fmt = mode === 'cpu' ? fmtCPU : fmtMem

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />

        <XAxis
          dataKey="ts"
          tickFormatter={fmtTime}
          tick={{ fill: CHART.tick, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          minTickGap={60}
        />
        <YAxis
          tickFormatter={fmt}
          tick={{ fill: CHART.tick, fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={70}
        />

        <Tooltip content={<CustomTooltip mode={mode} />} />

        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
          formatter={(v) => <span style={{ color: CHART.tick }}>{v}</span>}
        />

        {/* Recommended band (shaded) */}
        {recReq != null && (
          <ReferenceLine
            y={recReq}
            stroke={CHART.rec}
            strokeDasharray="6 3"
            label={{ value: `Rec ${fmt(recReq)}`, fill: CHART.rec, fontSize: 10, position: 'right' }}
          />
        )}

        {/* Actual usage — primary solid line */}
        <Area
          type="monotone"
          dataKey="usage"
          name="Actual usage"
          stroke={CHART.usage}
          fill={CHART.usage + '1a'}
          strokeWidth={CHART.strokeWidth}
          dot={false}
          activeDot={{ r: CHART.activeDot }}
        />

        {/* Current request — dashed */}
        <Line
          type="monotone"
          dataKey="request"
          name="Current request"
          stroke={CHART.request}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          dot={false}
        />

        {/* Current limit — dotted subtle */}
        <Line
          type="monotone"
          dataKey="limit"
          name="Current limit"
          stroke={CHART.limit}
          strokeWidth={1}
          strokeDasharray="2 4"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
