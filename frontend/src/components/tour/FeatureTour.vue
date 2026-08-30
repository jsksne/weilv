<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import type { ViewId } from '@/contracts'

/**
 * 新手教程：游戏式聚光引导。第一次进入应用自动运行（App.vue 控制），
 * 之后可通过左下角「新手教程」按钮重新唤起。每一步聚光一个真实组件，
 * 讲清它能做什么；目标不在当前页时先切页再聚光。
 */

interface TourStep {
  view: ViewId
  target: string
  title: string
  desc: string
}

const STEPS: readonly TourStep[] = [
  { view: 'today', target: '[data-testid="hero-progress"]', title: '今日 · 进度', desc: '这里是你的专属首页。完成一件微任务，这里的进度就会如实 +1。' },
  { view: 'today', target: '.observe-card', title: '微律观察', desc: '有真实记录后，这里会整理你的状态观察；没有数据时不会替你猜。' },
  { view: 'today', target: '.mood-card', title: '心情与可用时间', desc: '选此刻的心情和课后可用时间，微律会据此重新生成真实推荐。' },
  { view: 'today', target: '.task-card', title: '今日微任务', desc: '来自审核白名单的小任务。「开始」「先跳过」都可以，部分完成也算数。' },
  { view: 'today', target: '.breath-card', title: '跟随呼吸', desc: '9 秒一循环的呼吸节律，紧张或累的时候，跟着这颗球一起呼吸。' },
  { view: 'today', target: '.rhythm-card', title: '今天的节奏', desc: '有真实节奏数据后，会按你的习惯把建议轻轻排进一天里。' },
  { view: 'assistant', target: '.ask-hero', title: '有事，问问薇薇', desc: '把困扰说给薇薇，她会拆解问题、检索审核知识库，再给出建议。' },
  { view: 'assistant', target: '[data-testid="quick-prompts"]', title: '快捷提问', desc: '不知道怎么开口时，点一个常见场景直接开始。' },
  { view: 'assistant', target: '[data-testid="chat-composer"]', title: '输入框', desc: '在这里输入你现在的状态，每一歩的处理状态都会如实显示。' },
  { view: 'profile', target: '.profile-grid', title: '我的画像', desc: '只展示真实 Profile、任务记录和已授权记忆，没有数据不会用演示内容填充。' },
  { view: 'weekly', target: '.week-wrap .card', title: '周度变化', desc: '每周只读统计：完成任务分钟数、调整轨迹与本周小结。' },
]

const TOUR_STORAGE_KEY = 'weilv-tour-done'

const props = defineProps<{
  /** 切页回调（App 绑定 AppShell.switchView）。 */
  navigate: (view: ViewId) => void
}>()

const emit = defineEmits<{
  done: []
}>()

const visible = ref(false)
const index = ref(0)
const spot = ref({ top: 0, left: 0, width: 0, height: 0 })
const cardPos = ref({ top: 0, left: 0 })
/** 首次测量完成前隐藏卡片，避免 (0,0) 闪现与跳位。 */
const placed = ref(false)
const targetMissing = ref(false)

const step = (): TourStep => STEPS[index.value]!
const total = STEPS.length

function isTourDone(): boolean {
  try {
    return window.localStorage.getItem(TOUR_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function markTourDone(): void {
  try {
    window.localStorage.setItem(TOUR_STORAGE_KEY, '1')
  } catch {
    /* storage 不可用时每次都允许运行 */
  }
}

function hasStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function start(): void {
  index.value = 0
  visible.value = true
  void place()
}

function finish(): void {
  visible.value = false
  markTourDone()
  emit('done')
}

function next(): void {
  if (index.value >= total - 1) finish()
  else index.value += 1
}

function back(): void {
  if (index.value > 0) index.value -= 1
}

function onKey(event: KeyboardEvent): void {
  if (!visible.value) return
  if (event.key === 'Escape') finish()
  else if (event.key === 'ArrowRight' || event.key === 'Enter') next()
}

function reposition(): void {
  if (!visible.value) return
  /* 用户滚动时只重算位置，不再触发自动滚动（避免循环）。 */
  void place({ autoScroll: false })
}

async function place(options: { autoScroll?: boolean } = {}): Promise<void> {
  const current = step()
  placed.value = false
  await nextTick()
  /* 目标组件不在当前页：先切页，等新页渲染后再聚光。 */
  const active = document.querySelector('.view.active')?.getAttribute('data-view')
  if (active && active !== current.view) {
    props.navigate(current.view)
    /* 切页后等渲染稳定再测量，避免拿到 display:none 的旧位置。 */
    await new Promise(resolve => setTimeout(resolve, 380))
  }
  if (!visible.value) return
  const el = document.querySelector(current.target)
  if (!el) {
    targetMissing.value = true
    spot.value = { top: 0, left: 0, width: 0, height: 0 }
    cardPos.value = { top: window.innerHeight * 0.3, left: Math.max(16, (window.innerWidth - 320) / 2) }
    placed.value = true
    return
  }
  targetMissing.value = false
  /* 折叠区下方的目标先滚进视口，否则聚光框和卡片都会落在视口外。 */
  if (options.autoScroll !== false) {
    const raw = el.getBoundingClientRect()
    if (raw.top < 80 || raw.bottom > window.innerHeight - 80) {
      el.scrollIntoView({ block: 'center' })
      await new Promise(resolve => setTimeout(resolve, 320))
    }
  }
  const rect = el.getBoundingClientRect()
  const pad = 8
  spot.value = {
    top: Math.max(0, rect.top - pad),
    left: Math.max(0, rect.left - pad),
    width: rect.width + pad * 2,
    height: rect.height + pad * 2,
  }
  const cardWidth = 320
  const cardHeight = 190
  const below = rect.bottom + 14
  const top = below + cardHeight < window.innerHeight ? below : Math.max(14, rect.top - cardHeight - 14)
  const left = Math.min(Math.max(16, rect.left), window.innerWidth - cardWidth - 16)
  cardPos.value = { top, left }
  placed.value = true
}

watch(index, () => {
  void place()
})

watch(visible, value => {
  if (typeof window === 'undefined') return
  if (value) {
    window.addEventListener('scroll', reposition, { passive: true })
    window.addEventListener('resize', reposition)
    window.addEventListener('keydown', onKey)
  } else {
    window.removeEventListener('scroll', reposition)
    window.removeEventListener('resize', reposition)
    window.removeEventListener('keydown', onKey)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('scroll', reposition)
    window.removeEventListener('resize', reposition)
    window.removeEventListener('keydown', onKey)
  }
})

defineExpose({ start, isTourDone, hasStorage })
</script>

<template>
  <div v-if="visible" class="tour-overlay" data-testid="feature-tour" @click.self="finish">
    <div class="tour-spot" :style="{ top: `${spot.top}px`, left: `${spot.left}px`, width: `${spot.width}px`, height: `${spot.height}px` }"></div>
    <div
      class="tour-card"
      :style="{ top: `${cardPos.top}px`, left: `${cardPos.left}px`, visibility: placed ? 'visible' : 'hidden' }"
      role="dialog"
      aria-label="新手教程"
    >
      <span class="tour-step-no">新手教程 · {{ index + 1 }} / {{ total }}</span>
      <h3>{{ step().title }}</h3>
      <p>{{ step().desc }}</p>
      <div class="tour-actions">
        <button v-if="index > 0" class="btn btn-ghost" type="button" data-action="tour-back" @click="back">
          上一步
        </button>
        <button class="btn btn-primary btn-sm" type="button" data-action="tour-next" @click="next">
          {{ index >= total - 1 ? '完成' : '下一步' }}
        </button>
        <button class="btn btn-ghost tour-skip" type="button" data-action="tour-skip" @click="finish">
          跳过教程
        </button>
      </div>
    </div>
  </div>
</template>
