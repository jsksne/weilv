<script setup lang="ts">
import { useWeeklyChart, type WeeklyChartInput } from '@/composables/useWeeklyChart'
import type { WeeklyContract } from '@/contracts'

const props = defineProps<{
  model: Pick<WeeklyContract, 'chart' | 'days' | 'minutes'>
}>()

const chart = useWeeklyChart((): WeeklyChartInput => props.model)
</script>

<template>
  <div class="card chart-card" data-testid="weekly-chart">
    <div class="chart-head">
      <h3>{{ model.chart.title }}</h3>
      <span>{{ model.chart.note }}</span>
    </div>
    <svg
      class="chart-svg"
      :viewBox="chart.viewBox"
      role="img"
      aria-label="周一至周日完成任务分钟趋势"
    >
      <defs>
        <linearGradient id="areaGrad2" x1="0" y1="0" x2="0" y2="240" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="rgba(255,183,197,0.35)" />
          <stop offset="1" stop-color="rgba(255,183,197,0)" />
        </linearGradient>
      </defs>
      <path v-if="chart.areaPath" class="chart-area" :d="chart.areaPath" />
      <path v-if="chart.linePath" class="chart-line" :d="chart.linePath" />
      <template v-for="(point, index) in chart.points" :key="`${point.label}-${index}`">
        <circle
          class="chart-point"
          :cx="point.x"
          :cy="point.y"
          r="5.5"
          fill="#fff"
          :stroke="point.color"
          stroke-width="3"
          :style="{ animationDelay: `${0.25 + index * 0.16}s` }"
        />
        <text
          class="chart-value"
          :x="point.x"
          :y="point.valueY"
          text-anchor="middle"
          :style="{ animationDelay: `${0.4 + index * 0.16}s` }"
        >{{ point.valueLabel }}</text>
      </template>
      <text
        v-for="label in chart.labels"
        :key="label.text"
        class="chart-day"
        :x="label.x"
        :y="label.y"
        text-anchor="middle"
      >{{ label.text }}</text>
    </svg>
    <p v-if="!chart.points.length" class="weekly-empty" data-testid="weekly-chart-empty">
      暂无可展示的周度记录
    </p>
  </div>
</template>
