<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

import type { TodayContract, TodayTaskView } from '@/contracts'
import type { DailyTaskEntry, DailyTasksController } from '@/composables/useDailyTasks'
import { useMotionPulse } from '@/composables/useMotionPulse'
import { useToast } from '@/composables/useToast'
import TaskCompletionFx from '@/components/effects/TaskCompletionFx.vue'

/**
 * 冻结原型任务卡（923-963 行 + 交互脚本 1440-1496 行）。
 *
 * - 按钮组随 actions stage 渲染（原型按 innerHTML 替换的四种形态）；
 * - done：badge/done-note/进度由 controller 驱动，卡片 scale(1+0.02v)
 *   950ms 脉冲 + TaskCompletionFx（.task-state 视觉中心）；
 * - partial：较轻 scale(1+0.012v) 700ms 脉冲；
 * - start：translateY(-3v) 700ms 脉冲；
 * - replace：rise 450ms 左移淡出 → 470ms 换内容 → decay 600ms 回位
 *   （displayTask 本地镜像延迟切换，其余内容变更即时跟随）；
 * - 冷却由 controller 判定，cooldown 结果不产生任何视觉反馈（与原型一致）。
 */
const props = defineProps<{
  entry: DailyTaskEntry
  controller: DailyTasksController
  copy: TodayContract['feedbackCopy']
  canReplace?: boolean
}>()

const { play, delay, dispose } = useMotionPulse()
const { push } = useToast()

const toneClass = computed(() =>
  props.entry.task.tone === 'default' ? undefined : `t-${props.entry.task.tone}`,
)
const stateClass = computed(() => {
  if (props.entry.interaction === 'done') return 'done'
  if (props.entry.interaction === 'partial') return 'partial'
  if (props.entry.interaction === 'skipped') return 'skippedcard'
  return undefined
})

const badgeText = computed(() => {
  if (props.entry.interaction === 'partial') return '部分完成 · 也算数哦'
  if (props.entry.interaction === 'skipped') return '跳过了 · 没关系呀'
  return '完成 · 今天的花瓣 +1'
})

const doneNote = computed(() =>
  props.entry.interaction === 'partial' ? '🌱 部分完成 · 已记下' : '🌸 已记下 · 今天的一片花瓣',
)

/* ---------- replace 动画的本地内容镜像 ---------- */

const replacePhase = ref<'idle' | 'out' | 'in'>('idle')
const displayTask = ref<TodayTaskView>(props.entry.task)

watch(
  () => props.entry.task,
  task => {
    if (replacePhase.value === 'idle') displayTask.value = task
  },
)

/* ---------- 卡片运动样式（脉冲 + 换卡两相） ---------- */

const pulseTransform = ref('')
const cardStyle = computed(() => {
  if (replacePhase.value === 'out') {
    return {
      transform: 'translateX(-40px) rotate(-1.5deg)',
      opacity: '0',
      transition: 'transform .45s var(--ease-rise), opacity .45s var(--ease-rise)',
    }
  }
  if (replacePhase.value === 'in') {
    return {
      transform: 'none',
      opacity: '1',
      transition: 'transform .6s var(--ease-decay), opacity .6s var(--ease-decay)',
    }
  }
  return pulseTransform.value ? { transform: pulseTransform.value } : undefined
})

/* ---------- 完成特效 ---------- */

const fx = ref<InstanceType<typeof TaskCompletionFx> | null>(null)
const taskState = ref<HTMLElement | null>(null)

function playCompletionFx(): void {
  const rect = taskState.value?.getBoundingClientRect()
  if (!rect) return
  fx.value?.play(rect.left + rect.width / 2, rect.top + rect.height / 2)
}

/* ---------- 动作分发 ---------- */

function pulseCard(durationMs: number, scale: (v: number) => string): void {
  play(
    durationMs,
    v => {
      pulseTransform.value = scale(v)
    },
    () => {
      pulseTransform.value = ''
    },
  )
}

function animateReplace(): void {
  replacePhase.value = 'out'
  delay(470, () => {
    displayTask.value = props.entry.task
    replacePhase.value = 'in'
    delay(600, () => {
      replacePhase.value = 'idle'
      displayTask.value = props.entry.task
    })
  })
}

function notify(message: string): void {
  if (message) push(message)
}

function run(act: 'start' | 'done' | 'partial' | 'skip' | 'restore' | 'replace'): void {
  const slotId = props.entry.slotId
  const method = act === 'done' ? 'complete' : act
  const result = props.controller[method](slotId)
  if (result !== 'applied') return

  if (act === 'start') {
    pulseCard(700, v => `translateY(${-3 * v}px)`)
    notify(props.copy.start)
    return
  }
  if (act === 'done') {
    playCompletionFx()
    pulseCard(950, v => `scale(${1 + 0.02 * v})`)
    notify(props.copy.done)
    return
  }
  if (act === 'partial') {
    pulseCard(700, v => `scale(${1 + 0.012 * v})`)
    notify(props.copy.partial)
    return
  }
  if (act === 'skip') {
    notify(props.copy.skip)
    return
  }
  if (act === 'replace') {
    animateReplace()
    notify(props.copy.replace)
  }
  /* restore：原型无反馈 */
}

onUnmounted(dispose)
</script>

<template>
  <article class="card task-card" :class="[toneClass, stateClass]" :style="cardStyle">
    <div class="task-top">
      <span class="task-domain">{{ displayTask.domain }}</span>
      <span class="task-meta">{{ displayTask.meta }}</span>
    </div>
    <h3 class="task-name">{{ displayTask.name }}</h3>
    <p class="task-desc">{{ displayTask.description }}</p>
    <div class="task-why">
      <span class="why-icon"><svg class="ic"><use :href="`#${displayTask.whyIcon}`" /></svg></span>
      <div>
        <b>为什么是它</b>
        <p>{{ displayTask.why }}</p>
      </div>
    </div>

    <div class="task-actions">
      <template v-if="entry.actions === 'initial'">
        <button class="btn btn-primary" type="button" data-act="start" @click="run('start')">开始</button>
        <button
          v-if="canReplace"
          class="btn btn-ghost"
          type="button"
          data-act="replace"
          @click="run('replace')"
        >换一朵</button>
        <button class="btn btn-ghost" type="button" data-act="skip" @click="run('skip')">先跳过</button>
      </template>
      <template v-else-if="entry.actions === 'active'">
        <button class="btn btn-ok" type="button" data-act="done" @click="run('done')">✓ 完成啦</button>
        <button class="btn btn-ghost" type="button" data-act="partial" @click="run('partial')">部分完成</button>
        <button
          v-if="canReplace"
          class="btn btn-ghost"
          type="button"
          data-act="replace"
          @click="run('replace')"
        >换一朵</button>
        <button class="btn btn-ghost" type="button" data-act="skip" @click="run('skip')">先跳过</button>
      </template>
      <template v-else-if="entry.actions === 'restore'">
        <button class="btn btn-ghost" type="button" data-act="restore" @click="run('restore')">恢复它</button>
      </template>
      <span v-else class="done-note">{{ doneNote }}</span>
    </div>

    <div ref="taskState" class="task-state">
      <svg viewBox="0 0 46 46">
        <circle class="ck-ring" cx="23" cy="23" r="21" />
        <path class="ck-path" d="M14 24 L20.5 30.5 L33 16.5" />
      </svg>
    </div>
    <div class="task-badge">
      <span class="bdot"></span>
      <span class="badge-txt">{{ badgeText }}</span>
    </div>

    <TaskCompletionFx ref="fx" />
  </article>
</template>
