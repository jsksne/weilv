<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import type { TodayContextSelection, TodayContract } from '@/contracts'
import type { DailyTaskEntry, DailyTasksController, TaskActionOutcome } from '@/composables/useDailyTasks'
import { useToast } from '@/composables/useToast'
import DockedTaskProgress from '@/components/shell/DockedTaskProgress.vue'
import BreathCard from '@/components/today/BreathCard.vue'
import DailyCheckCard from '@/components/today/DailyCheckCard.vue'
import ObservationCard from '@/components/today/ObservationCard.vue'
import RhythmTimeline from '@/components/today/RhythmTimeline.vue'
import TaskList from '@/components/today/TaskList.vue'
import TaskRunPanel from '@/components/today/TaskRunPanel.vue'
import ScheduleCard from '@/components/today/ScheduleCard.vue'
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
  /** 日程最小实现：Production 由 App 传入 DataSource。 */
  dataSource?: import('@/contracts').UiDataSource
  /** F6：完成后轻反馈（Production 由 App 传正式链路）。 */
  submitLightFeedback?: (
    task: import('@/contracts').TodayTaskView,
    completionStatus: 'completed' | 'partially_completed',
    usefulness: 'helpful' | 'neutral' | 'not_helpful',
  ) => Promise<{ status: string }>
}>()

const emit = defineEmits<{
  'context-change': [context: TodayContextSelection]
}>()

/* ---------- F3：执行面板（关闭不结束任务） ---------- */
const panelEntry = ref<DailyTaskEntry | null>(null)
const panelBusy = ref(false)

async function runFor(entry: DailyTaskEntry, action: 'complete' | 'partial' | 'skip'): Promise<boolean> {
  panelBusy.value = true
  try {
    const outcome: TaskActionOutcome = props.daily[action](entry.slotId)
    const result = outcome instanceof Promise ? await outcome : outcome
    return result === 'applied'
  } finally {
    panelBusy.value = false
  }
}

async function onPanelDone(): Promise<void> {
  if (!panelEntry.value) return
  if (await runFor(panelEntry.value, 'complete')) panelEntry.value = null
}

async function onPanelPartial(): Promise<void> {
  if (!panelEntry.value) return
  if (await runFor(panelEntry.value, 'partial')) panelEntry.value = null
}

async function onPanelPause(): Promise<void> {
  if (!panelEntry.value) return
  const entry = panelEntry.value
  if (await runFor(entry, 'skip')) {
    panelEntry.value = null
    push('先放下了；这张卡还在，随时可以恢复它')
  }
}

/* ---------- F5：现在不适合——原因进入本次正式约束 ---------- */
const unsuitableEntry = ref<DailyTaskEntry | null>(null)

function applyUnsuitable(reason: 'no_time' | 'cannot_move' | 'avoid_kind' | 'done_similar'): void {
  unsuitableEntry.value = null
  const base = {
    mood: props.daily.mood.value,
    availableMinutes: props.daily.availableMinutes.value,
  }
  if (reason === 'no_time') {
    emit('context-change', { ...base, availableMinutes: 2 })
    push('只保留 2 分钟内能完成的选择')
    return
  }
  if (reason === 'cannot_move') {
    emit('context-change', { ...base, cannotMove: true })
    push('接下来换成不需要起身的一项')
    return
  }
  emit('context-change', { ...base })
  push(reason === 'done_similar' ? '今天先不重复类似的活动' : '正在为你换一批')
}

const { push } = useToast()

const hero = ref<InstanceType<typeof TodayHero> | null>(null)
const checkCard = ref<InstanceType<typeof DailyCheckCard> | null>(null)
const taskArea = ref<HTMLElement | null>(null)

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

async function focusTask(taskId: string): Promise<boolean> {
  await nextTick()
  const target = Array.from(
    taskArea.value?.querySelectorAll<HTMLElement>('[data-task-id]') ?? [],
  ).find(card => card.dataset.taskId === taskId)
  if (!target) return false

  target.focus({ preventScroll: true })
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
  return true
}

defineExpose({ focusTask })
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

  <ScheduleCard v-if="model.state.mode === 'production' && dataSource" :data-source="dataSource" />

  <div class="card observe-card">
    <ObservationCard :observation="model.observation" />
  </div>

  <div class="today-grid">
    <div ref="taskArea">
      <DailyCheckCard
        ref="checkCard"
        :model="model"
        :mood="daily.mood.value"
        :available-minutes="daily.availableMinutes.value"
        @select-mood="onSelectMood"
        @select-time="onSelectTime"
      />
      <TaskList
        :model="model"
        :controller="daily"
        :submit-light-feedback="submitLightFeedback"
        @open-panel="panelEntry = $event"
        @unsuitable="unsuitableEntry = $event"
      />
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

  <TaskRunPanel
    v-if="panelEntry"
    :entry="panelEntry"
    :submitting="panelBusy"
    @close="panelEntry = null"
    @done="onPanelDone"
    @partial="onPanelPartial"
    @pause="onPanelPause"
  />

  <div
    v-if="unsuitableEntry"
    class="run-mask"
    data-testid="unsuitable-panel"
    role="dialog"
    aria-modal="true"
    aria-label="告诉我们为什么不合适"
    @click.self="unsuitableEntry = null"
  >
    <div class="card run-card">
      <h3 class="run-name">现在为什么不合适？</h3>
      <p class="run-note">选择只会影响这一次推荐，不会记成长期偏好。</p>
      <div class="run-actions">
        <button class="btn btn-ghost" type="button" data-reason="no_time" @click="applyUnsuitable('no_time')">时间不够</button>
        <button class="btn btn-ghost" type="button" data-reason="cannot_move" @click="applyUnsuitable('cannot_move')">场合不方便</button>
        <button class="btn btn-ghost" type="button" data-reason="avoid_kind" @click="applyUnsuitable('avoid_kind')">今天不想做这类</button>
        <button class="btn btn-ghost" type="button" data-reason="done_similar" @click="applyUnsuitable('done_similar')">今天已经做过类似</button>
        <button class="btn btn-ghost" type="button" data-reason="cancel" @click="unsuitableEntry = null">先不换了</button>
      </div>
    </div>
  </div>
</template>
