import { computed, toValue, type ComputedRef, type MaybeRefOrGetter } from 'vue'

import type { WeeklyContract } from '@/contracts'

export const WEEKLY_CHART = {
  width: 640,
  height: 240,
  padding: { top: 42, right: 100, bottom: 20, left: 60 },
} as const

const POINT_COLORS = ['#c4a5b1', '#f78fb0', '#9d7bdf', '#7cc6b7'] as const

export type WeeklyChartInput = Pick<WeeklyContract, 'days' | 'minutes'>

export interface WeeklyChartPoint {
  label: string
  minutes: number
  x: number
  y: number
  valueY: number
  valueLabel: string
  color: string
}

export interface WeeklyChartLabel {
  text: string
  x: number
  y: number
}

export interface WeeklyChartModel {
  viewBox: string
  baselineY: number
  linePath: string
  areaPath: string
  points: readonly WeeklyChartPoint[]
  labels: readonly WeeklyChartLabel[]
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}

export function createWeeklyChart(input: WeeklyChartInput): WeeklyChartModel {
  const { days, minutes } = input
  const count = Math.min(days.length, minutes.length)
  const { width, height, padding } = WEEKLY_CHART
  const baselineY = height - padding.bottom
  const chartHeight = baselineY - padding.top
  const chartWidth = width - padding.left - padding.right
  const samples = Array.from({ length: count }, (_, index) => ({
    label: days[index] ?? '',
    minutes: Number.isFinite(minutes[index]) ? Math.max(0, minutes[index] ?? 0) : 0,
  }))
  const maxMinutes = Math.max(...samples.map(sample => sample.minutes), 1)

  const points = samples.map((sample, index) => {
    const x = count === 1 ? padding.left : padding.left + (chartWidth * index) / (count - 1)
    const y = baselineY - (sample.minutes / maxMinutes) * chartHeight

    return {
      label: sample.label,
      minutes: sample.minutes,
      x: round(x),
      y: round(y),
      valueY: round(Math.max(18, y - 14)),
      valueLabel: sample.minutes === 0 ? '—' : `${sample.minutes}′`,
      color: POINT_COLORS[index % POINT_COLORS.length] ?? POINT_COLORS[0],
    }
  })
  const linePath = points.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x} ${point.y}`).join(' ')
  const firstPoint = points[0]
  const lastPoint = points[points.length - 1]
  const areaPath = firstPoint && lastPoint
    ? `${linePath} L${lastPoint.x} ${baselineY} L${firstPoint.x} ${baselineY} Z`
    : ''

  return {
    viewBox: `0 0 ${width} ${height}`,
    baselineY,
    linePath,
    areaPath,
    points,
    labels: points.map(point => ({ text: point.label, x: point.x, y: height - 4 })),
  }
}

export function useWeeklyChart(
  input: MaybeRefOrGetter<WeeklyChartInput>,
): ComputedRef<WeeklyChartModel> {
  return computed(() => createWeeklyChart(toValue(input)))
}
