<script setup lang="ts">
import { computed, ref } from 'vue'

import type { TodayContextSelection, TodayContract } from '@/contracts'
import type { DailyTasksController } from '@/composables/useDailyTasks'
import { useToast } from '@/composables/useToast'
import DockedTaskProgress from '@/components/shell/DockedTaskProgress.vue'
import BreathCard from '@/components/today/BreathCard.vue'
import DailyCheckCard from '@/components/today/DailyCheckCard.vue'
import ObservationCard from '@/components/today/ObservationCard.vue'
import RhythmTimeline from '@/components/today/RhythmTimeline.vue'
import TaskList from '@/components/today/TaskList.vue'
import TodayHero from '@/components/today/TodayHero.vue'

/**
 * 冻结原型 #view-today（864-987 行）的 Vue 组合根。
 *
 * DOM 结构逐块对应：.hero.stagger → .card.observe-card → .today-grid
 * （左：心情卡 + 任务列表；右：呼吸卡 + 节奏卡）；组件化只改变代码组织。
 *
 * 状态：daily（useDailyTasks，App 层创建的唯一实例）为今日进度唯一
 * 状态源——hero 进度行与吸附顶栏都从这里取数。
 */
const props = defineProps<{
  model: TodayContract
  daily: DailyTasksController
}>()

const emit = defineEmits<{
  'context-change': [context: TodayContextSelection]
}>()

const { push } = useToast()

const hero = ref<InstanceType<typeof TodayHero> | null>(null)
const checkCard = ref<InstanceType<typeof DailyCheckCard> | null>(null)

const dockedSentinel = computed(() => hero.value?.progressRow ?? null)
const dockedProgress = computed(() => ({
  completed: props.daily.completed.value,
  total: props.daily.total.value,
  note: props.daily.dockedProgressNote.value,
}))

/* 原型 btnCheck：滚动聚焦心情卡 + 冻结 toast */
function onCheck(): void {
  checkCard.value?.focusCheck()
  push(props.model.feedbackCopy.check)
}

/* 原型 moodRow low 分支：每次点击 low 都提示（含重复点击） */
function onSelectMood(value: string): void {
  props.daily.applyMood(value)
  if (value === 'low') push(props.model.feedbackCopy.lowMood)
  emit('context-change', {
    mood: value,
    availableMinutes: props.daily.availableMinutes.value,
  })
}

function onSelectTime(minutes: number): void {
  props.daily.selectTime(minutes)
  emit('context-change', {
    mood: props.daily.mood.value,
    availableMinutes: minutes,
  })
}
</script>

<template>
  <div class="hero stagger">
    <TodayHero
      ref="hero"
      :model="model"
      :completed="daily.completed.value"
      :total="daily.total.value"
      :note="daily.heroProgressNote.value"
      @check="onCheck"
    />
  </div>

  <div class="card observe-card">
    <ObservationCard :observation="model.observation" />
  </div>

  <div class="today-grid">
    <div>
      <DailyCheckCard
        ref="checkCard"
        :model="model"
        :mood="daily.mood.value"
        :available-minutes="daily.availableMinutes.value"
        @select-mood="onSelectMood"
        @select-time="onSelectTime"
      />
      <TaskList :model="model" :controller="daily" />
      <p v-if="daily.pendingFeedback.value.length" data-testid="pending-feedback" role="status">
        当前页面已更新；详细反馈尚未提交。
      </p>
    </div>
    <aside>
      <BreathCard :breath="model.breath" />
      <RhythmTimeline :rhythm="model.rhythm" />
    </aside>
  </div>

  <DockedTaskProgress :progress="dockedProgress" :sentinel="dockedSentinel" />
</template>
