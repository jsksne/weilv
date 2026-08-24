import type { UiState } from './common'

export type WeeklyDataAvailability = 'available' | 'unavailable'
export type WeeklyTimelineStatus = 'completed' | 'skipped' | 'adjusted'

export interface WeeklyHeader {
  title: string
  description: string
}

export interface WeeklyChartCopy {
  title: string
  note: string
}

export interface WeeklyTimelineItem {
  id: string
  time: string
  action: string
  tag: string
  description: string
  status: WeeklyTimelineStatus
}

export interface WeeklyTextSegment {
  text: string
  emphasis?: boolean
}

export interface WeeklyInsight {
  title: string
  segments: readonly WeeklyTextSegment[]
  quote: string
}

export interface WeeklyContract {
  state: UiState
  dataAvailability: WeeklyDataAvailability
  header: WeeklyHeader
  chart: WeeklyChartCopy
  days: readonly string[]
  minutes: readonly number[]
  timelineTitle: string
  timeline: readonly WeeklyTimelineItem[]
  insight: WeeklyInsight
}
