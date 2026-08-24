import { createWeeklyChart } from './composables/useWeeklyChart'
import { weeklyFixture } from './data/fixtures/weekly.fixture'

describe('Weekly chart computation', () => {
  it('derives paths, points and labels from the supplied minutes', () => {
    const chart = createWeeklyChart(weeklyFixture)
    const changed = createWeeklyChart({
      days: weeklyFixture.days,
      minutes: [0, 2, 4, 3, 6, 9, 8],
    })

    expect(chart.points).toHaveLength(7)
    expect(chart.labels).toHaveLength(7)
    expect(chart.linePath).toMatch(/^M/)
    expect(chart.areaPath).toMatch(/Z$/)
    expect(chart.points[1]?.y).not.toBe(changed.points[1]?.y)
    expect(chart.points.map(point => point.x)).toEqual([60, 140, 220, 300, 380, 460, 540])
    expect(`${chart.linePath} ${chart.areaPath}`).not.toMatch(/NaN|undefined/)
  })

  it('scales partial data without filling missing days', () => {
    const chart = createWeeklyChart({
      days: ['周一', '周二', '周三'],
      minutes: [10, 5, 0],
    })

    expect(chart.points).toHaveLength(3)
    expect(chart.labels).toHaveLength(3)
    expect(chart.points.at(-1)?.x).toBe(540)
    expect(chart.linePath).not.toMatch(/NaN|undefined/)
  })

  it('returns an empty model for empty data', () => {
    const chart = createWeeklyChart({ days: [], minutes: [] })

    expect(chart.points).toEqual([])
    expect(chart.labels).toEqual([])
    expect(chart.linePath).toBe('')
    expect(chart.areaPath).toBe('')
  })
})
