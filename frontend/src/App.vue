<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import TodayView from '@/views/TodayView.vue'
import AssistantView from '@/views/AssistantView.vue'
import ProfileView from '@/views/ProfileView.vue'
import WeeklyView from '@/views/WeeklyView.vue'
import { useDailyTasks } from '@/composables/useDailyTasks'
import { hasDemoOnboardingCompleted } from '@/composables/useOnboarding'
import { useMotionPulse } from '@/composables/useMotionPulse'
import { useToast } from '@/composables/useToast'
import { useUiDataSource } from '@/composables/useUiDataSource'
import { createUiDataSource } from '@/data/createUiDataSource'
import { createProductionShellContract, createUnavailableTodayContract } from '@/data/adapters'
import { getConfiguredApiBaseUrl } from '@/config/apiBaseUrl'
import { getConfiguredRecommendationContext } from '@/config/recommendationContext'
import { getConfiguredUiMode, UiModeConfigurationError } from '@/config/uiMode'
import { getConfiguredUserId, UserContextConfigurationError } from '@/config/userContext'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow.vue'
import StartupLoading from '@/components/StartupLoading.vue'
import FeatureTour from '@/components/tour/FeatureTour.vue'
import type {
  AssistantSuggestedTask,
  ShellContract,
  SuggestedTaskState,
  TodayContextSelection,
  TodayTaskAction,
  TodayTaskView,
  UiDataSource,
  ViewId,
} from '@/contracts'
import type {
  OnboardingSubmitAnswers,
  OnboardingSubmitResult,
} from '@/contracts'

/**
 * Sprint 9.1：正式集成入口，唯一的应用运行路径。
 * Demo → FixtureUiDataSource（fixture only）；Production → ApiUiDataSource（API only）。
 * Production 用户身份来自显式 VITE_USER_ID（可替换 integration seam，非认证系统）。
 * 旧组件/旧 CSS/旧 flow 源码保留在仓库，但不再挂载、不再作为 alternate runtime。
 */

const configurationError = ref<Error | null>(null)
let dataSource: UiDataSource | null = null
try {
  const mode = getConfiguredUiMode()
  const options =
    mode === 'production'
      ? {
          userId: getConfiguredUserId(),
          recommendationContext: getConfiguredRecommendationContext(),
        }
      : {}
  if (mode === 'production') getConfiguredApiBaseUrl()
  dataSource = createUiDataSource(mode, options)
} catch (cause) {
  configurationError.value =
    cause instanceof UiModeConfigurationError || cause instanceof UserContextConfigurationError
      ? cause
      : cause instanceof Error
        ? cause
        : new Error('UI 配置无效。')
}

const ui = useUiDataSource(dataSource, {
  autoLoad: !configurationError.value,
})
if (configurationError.value) {
  ui.status.value = 'error'
  ui.error.value = configurationError.value
}
const { status, retry } = ui
const errorMessage = computed(() => ui.error.value?.message ?? 'UI 数据配置或加载失败。')

const bundle = computed(() => ui.data.value)
const today = computed(() => bundle.value?.today ?? createUnavailableTodayContract('UI 数据加载中。'))

/**
 * Sprint 9：Production 任务动作 → B2 事件（用该任务自己的 recommendation_id）。
 * F4：完成/部分完成保存成功后局部刷新周报与画像概览；
 * 刷新失败不撤销已保存的任务。
 */
function onTaskAction(task: TodayTaskView, action: TodayTaskAction): Promise<{ status: string }> {
  if (!task.recommendationId || !dataSource?.submitTaskAction) {
    return Promise.resolve({ status: 'error' })
  }
  const result = dataSource.submitTaskAction(task.recommendationId, action)
  if (action === 'completed' || action === 'partially_completed') {
    void result.then(reply => {
      if (reply.status === 'recorded' || reply.status === 'demo_local') {
        void ui.refreshPartial(['weekly', 'profile'])
      }
    })
  }
  return result
}

/**
 * F6：完成后一次轻反馈 → 正式反馈端点。保存成功会写入用户记忆，
 * 影响后续个性化排序；失败只影响评价，不撤销完成状态。
 */
async function submitLightFeedback(
  task: TodayTaskView,
  completionStatus: 'completed' | 'partially_completed',
  usefulness: 'helpful' | 'neutral' | 'not_helpful',
): Promise<{ status: string }> {
  if (!task.recommendationId || !dataSource?.submitLightFeedback) return { status: 'error' }
  const difficulty = usefulness === 'neutral' ? 'difficult' : usefulness === 'helpful' ? 'easy' : 'suitable'
  return dataSource.submitLightFeedback(task.recommendationId, {
    completion_status: completionStatus,
    usefulness,
    difficulty,
    reason: '',
  })
}

/** 心情/时间变化后轻刷新今日推荐（防抖；只换 today 数据，不闪烁整页）。 */
const todayRefreshing = ref(false)
const { delay } = useMotionPulse()
const { push } = useToast()
let todayContextVersion = 0
function onTodayContextChange(context: TodayContextSelection): void {
  dataSource?.setTodayContext?.(context)
  const version = ++todayContextVersion
  todayRefreshing.value = true
  delay(800, () => {
    if (version !== todayContextVersion) return
    void refreshToday(version)
  })
}

async function refreshToday(version: number): Promise<void> {
  if (!dataSource) {
    todayRefreshing.value = false
    return
  }
  try {
    const nextToday = await dataSource.getToday()
    /* 只替换 today；profile/weekly 沿用当前数据，避免整页闪烁。 */
    if (ui.data.value && version === todayContextVersion) {
      ui.data.value = { ...ui.data.value, today: nextToday }
    }
  } catch {
    /* 刷新失败保留当前推荐；不打断用户。 */
  } finally {
    if (version === todayContextVersion) todayRefreshing.value = false
  }
}

/* 今日交互状态唯一实例：hero 进度行与吸附顶栏都从 DataSource Contract 取数 */
const daily = useDailyTasks(today, { onAction: onTaskAction })
const onboardingVisible = ref(false)
/** 本次会话内用户已主动关闭引导（跳过/完成）后，不再因数据重载重新弹出。 */
const onboardingDismissed = ref(false)
const onboarding = computed(() => ui.onboarding.value ?? bundle.value?.onboarding ?? null)

/*
 * Production 的 userId 是共享的 controlled identity（非认证系统），
 * 服务端 Profile 一旦存在就不再区分"新访客"。引导可见性改用浏览器本地
 * 首次标记：每个新浏览器/新访客都会看到一次引导，跳过或完成后不再打扰。
 */
const PROD_ONBOARDING_SEEN_KEY = 'weilv-prod-onboarding-seen'
function hasProdOnboardingSeen(): boolean {
  try {
    return window.localStorage.getItem(PROD_ONBOARDING_SEEN_KEY) === '1'
  } catch {
    return false
  }
}
function markProdOnboardingSeen(): void {
  try {
    window.localStorage.setItem(PROD_ONBOARDING_SEEN_KEY, '1')
  } catch {
    /* storage 不可用：仅影响下次是否再次展示 */
  }
}

watch(
  [() => ui.status.value, onboarding],
  ([status, model]) => {
    if (onboardingDismissed.value) return
    if (status === 'error') {
      onboardingVisible.value = false
      return
    }
    if (status === 'idle' || !model) return
    const isDemo = model.state.mode === 'demo'
    const firstVisit = isDemo
      ? !hasDemoOnboardingCompleted(model.storageKey)
      : !hasProdOnboardingSeen()
    if (firstVisit) {
      onboardingVisible.value = true
    }
  },
  { immediate: true },
)

/* Demo 保留冻结日期；Production 使用当前真实日期。 */
const frozenDateLabel = (): string => {
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][new Date().getDay()]
  return `4 月 22 日 · 星期${weekday}`
}

const currentDateLabel = (): string => {
  const now = new Date()
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][now.getDay()]
  return `${now.getMonth() + 1} 月 ${now.getDate()} 日 · 星期${weekday}`
}

const shell = computed<ShellContract>(() => {
  const base = bundle.value?.shell ?? createProductionShellContract()
  return {
    ...base,
    dateLabel: base.state.mode === 'demo' ? frozenDateLabel() : currentDateLabel(),
    progress: {
      completed: daily.completed.value,
      total: daily.total.value,
      note: daily.dockedProgressNote.value,
    },
  }
})

function openOnboarding(): void {
  onboardingVisible.value = true
}

function closeOnboarding(): void {
  onboardingVisible.value = false
}

/** 绑定 DataSource 方法到实例（避免解引用后 this 丢失）。 */
function submitOnboarding(
  answers: OnboardingSubmitAnswers,
): Promise<OnboardingSubmitResult> {
  return (
    dataSource?.submitOnboarding?.(answers) ??
    Promise.resolve({ status: 'error', message: '缺少 DataSource，无法保存引导结果。', persistence: [] })
  )
}

/**
 * Production 引导完成：重新加载 bundle（真实 Profile 已写入），
 * 由真实 Profile 状态驱动进入 Today。失败/跳过不假装完成。
 * 跳过与完成都写入本地"已见引导"标记；教程必须等 ui.reload() 完成、
 * FeatureTour 重新挂载后再启动（load 期间 ref 为 null，不能直接调度）。
 */
function onOnboardingComplete(): void {
  onboardingDismissed.value = true
  markProdOnboardingSeen()
  closeOnboarding()
  if (onboarding.value?.state.mode === 'production') {
    void ui.reload().then(() => startTourIfFirstVisit(900))
  } else {
    startTourIfFirstVisit(900)
  }
}

async function refreshProfile(): Promise<void> {
  if (dataSource && bundle.value?.profile.state.mode === 'production') await ui.load()
}

/* ---------- 新手教程 ---------- */
const shellRef = ref<InstanceType<typeof AppShell> | null>(null)
const todayRef = ref<InstanceType<typeof TodayView> | null>(null)
const tourRef = ref<InstanceType<typeof FeatureTour> | null>(null)

/** F2：建议卡按今日真实状态分流——去开始/继续/加入今日/今天已完成。 */
function resolveSuggestedState(taskId: string): SuggestedTaskState {
  const entry = daily.entries.value.find(item => item.task.taskId === taskId)
  if (!entry) return 'absent'
  if (entry.interaction === 'done' || entry.interaction === 'partial') return 'done'
  if (entry.interaction === 'started') return 'started'
  return 'pending'
}

function suggestedToTodayTask(task: AssistantSuggestedTask): TodayTaskView {
  const domains = task.domains ?? []
  const tone = domains.includes('eye_health') || domains.includes('light_recovery')
    ? 'eye' as const
    : domains.includes('sleep') || domains.includes('sleep_hygiene')
      ? 'sleep' as const
      : domains.some(domain => ['physical_activity', 'sedentary', 'neck_shoulder'].includes(domain))
        ? 'move' as const
        : 'default' as const
  return {
    id: task.taskId,
    taskId: task.taskId,
    recommendationId: task.recommendationId,
    tone,
    domain: domains[0] ?? '微任务',
    meta: task.meta,
    name: task.title,
    description: task.instruction ?? '按回答里的说明完成即可。',
    why: '来自本轮对话推荐，并已通过安全与适用检查。',
    whyIcon: 'flower',
  }
}

async function openSuggestedTask(task: AssistantSuggestedTask): Promise<void> {
  const state = resolveSuggestedState(task.taskId)
  if (state === 'done') {
    push('这件事今天已经完成了')
    return
  }
  if (state === 'absent') {
    /* 无真实执行记录时不假装已加入（不捏造 recommendationId）。 */
    if (!task.recommendationId) {
      push('这项建议暂未加入今日清单，可以先按回答里的步骤完成')
      return
    }
    daily.adoptSuggested(suggestedToTodayTask(task))
    push('已加入今日清单')
  }

  shellRef.value?.switchView('today')
  await nextTick()
  if (await todayRef.value?.focusTask(task.taskId)) {
    push(state === 'started' ? '继续这件事，做完就算数' : '已帮你找到这项任务')
  }
}

function navigateForTour(view: ViewId): void {
  shellRef.value?.switchView(view)
}

function startTour(): void {
  if (tourRef.value) {
    tourRef.value.start()
    return
  }
  /* load 期间组件短暂卸载：单次重试覆盖该竞态。 */
  delay(400, () => tourRef.value?.start())
}

/** 引导结束后自动运行一次新手教程；之后只能从左下角按钮唤起。 */
function startTourIfFirstVisit(delayMs: number): void {
  if (!tourRef.value?.hasStorage() || tourRef.value.isTourDone()) return
  delay(delayMs, startTour)
}

/* 存量用户（本地已见过引导）首次加载新版时，也自动看一次教程。 */
watch(
  [() => ui.status.value, onboardingVisible],
  ([status, visible]) => {
    if (status === 'ready' && !visible) startTourIfFirstVisit(1200)
  },
  { immediate: true },
)
</script>

<template>
  <AppShell
    v-if="status === 'ready' && bundle"
    ref="shellRef"
    :shell="shell"
    @replay="openOnboarding"
    @tour="startTour"
  >
    <template #today>
      <TodayView
        ref="todayRef"
        :model="bundle.today"
        :daily="daily"
        :data-source="dataSource ?? undefined"
        :submit-light-feedback="submitLightFeedback"
        @context-change="onTodayContextChange"
      />
    </template>
    <template #assistant>
      <AssistantView
        :model="bundle.assistant"
        :data-source="dataSource ?? undefined"
        :resolve-task-state="resolveSuggestedState"
        @activate-task="openSuggestedTask"
      />
    </template>
    <template #profile>
      <ProfileView
        :model="bundle.profile"
        :data-source="dataSource ?? undefined"
        :on-refresh="refreshProfile"
      />
    </template>
    <template #weekly>
      <WeeklyView :model="bundle.weekly" />
    </template>
  </AppShell>
  <StartupLoading v-else-if="status === 'loading'" :progress="ui.progress.value" />
  <section v-else data-testid="ui-data-error" role="alert">
    <p>{{ errorMessage }}</p>
    <button type="button" @click="retry">重试</button>
  </section>
  <OnboardingFlow
    v-if="onboardingVisible && onboarding"
    :model="onboarding"
    :submit="submitOnboarding"
    @complete="onOnboardingComplete"
  />
  <FeatureTour v-if="status === 'ready' && bundle" ref="tourRef" :navigate="navigateForTour" />
</template>
