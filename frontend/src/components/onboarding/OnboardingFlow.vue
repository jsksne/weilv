<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useMotionPulse } from '@/composables/useMotionPulse'
import { useOnboarding } from '@/composables/useOnboarding'
import { useToast } from '@/composables/useToast'
import type { OnboardingContract, OnboardingSubmitAnswers, OnboardingSubmitResult } from '@/contracts'

import OnboardingProgress from './OnboardingProgress.vue'
import OnboardingStep from './OnboardingStep.vue'
import ProfileGenerationStage from './ProfileGenerationStage.vue'

const props = withDefaults(defineProps<{
  model: OnboardingContract
  open?: boolean
  /** Production 提交通道（写 Profile）；Demo 不传，走本地完成。 */
  submit?: (answers: OnboardingSubmitAnswers) => Promise<OnboardingSubmitResult>
}>(), {
  open: true,
})

const emit = defineEmits<{
  complete: [status: 'completed' | 'skipped']
}>()

const flow = useOnboarding(props.model, props.submit)
const open = ref(props.open)
const closing = ref(false)
const dialog = ref<HTMLElement | null>(null)
let restoreFocusTo: HTMLElement | null = null
let previousBodyOverflow = ''
let pageScrollLocked = false
const { delay } = useMotionPulse()
const { push } = useToast()
const welcomeToast = '欢迎使用微律'

const currentNumber = computed(() => flow.index.value + 1)
const nextLabel = computed(() =>
  flow.isLast.value ? '进入微律' : flow.isFirst.value ? '开始认识你' : '下一步',
)
const mismatchMessage = computed(() => props.model.questionnaireCompatibility.message)
const submitting = computed(() => flow.phase.value === 'submitting')
const submitBlocked = computed(() => flow.phase.value === 'error' || flow.phase.value === 'unsupported')
const currentStepComplete = computed(() => {
  const step = flow.currentStep.value
  if (!step || step.kind !== 'choices') return true
  return (step.groups ?? []).every(group => {
    if (group.multiple) return true
    const answer = flow.answers[group.id]
    return typeof answer === 'string' && answer.length > 0
  })
})

function focusDialog(): void {
  const active = document.activeElement
  if (active instanceof HTMLElement && !dialog.value?.contains(active)) restoreFocusTo = active
  dialog.value?.focus()
}

function restoreDialogFocus(): void {
  restoreFocusTo?.focus()
  restoreFocusTo = null
}

function lockPageScroll(): void {
  if (pageScrollLocked) return
  previousBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  pageScrollLocked = true
}

function unlockPageScroll(): void {
  if (!pageScrollLocked) return
  document.body.style.overflow = previousBodyOverflow
  pageScrollLocked = false
}

function onDialogKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Tab' || !dialog.value) return
  const focusable = Array.from(
    dialog.value.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled])'),
  )
  if (focusable.length === 0) {
    event.preventDefault()
    dialog.value.focus()
    return
  }
  const first = focusable[0]!
  const last = focusable[focusable.length - 1]!
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(() => props.open, value => {
  open.value = value
  if (value) {
    lockPageScroll()
    focusDialog()
  } else {
    unlockPageScroll()
    restoreDialogFocus()
  }
})

onMounted(() => {
  if (open.value) {
    lockPageScroll()
    focusDialog()
  }
})

onBeforeUnmount(() => {
  unlockPageScroll()
  restoreDialogFocus()
})

async function finish(status: 'completed' | 'skipped'): Promise<void> {
  if (closing.value || submitting.value) return
  closing.value = true
  if (status === 'completed') {
    await flow.submit()
    if (submitBlocked.value) {
      closing.value = false
      return
    }
    push(welcomeToast)
  } else {
    flow.skip()
    push(welcomeToast)
  }
  emit('complete', status)
  delay(850, () => {
    unlockPageScroll()
    restoreDialogFocus()
    open.value = false
  })
}

async function next(): Promise<void> {
  if (!currentStepComplete.value) return
  if (flow.isLast.value) await finish('completed')
  else flow.next()
}

function skip(): void {
  void finish('skipped')
}
</script>

<template>
  <div
    v-if="open && model.totalSteps > 0"
    ref="dialog"
    class="onboard"
    :class="{ hide: closing }"
    data-testid="onboarding"
    role="dialog"
    aria-modal="true"
    aria-label="首次使用引导"
    tabindex="-1"
    @keydown="onDialogKeydown"
  >
    <div class="ob-card">
      <OnboardingProgress :current="currentNumber" :total="flow.total.value" />

      <!-- 每步渐入：key 变化重放 obStepIn（与原型 .ob-step.active 一致） -->
      <div :key="flow.index.value" class="ob-anim">
        <OnboardingStep
          v-if="flow.currentStep.value?.kind !== 'generation' && flow.currentStep.value"
          :step="flow.currentStep.value"
          :answers="flow.answers"
          @update-answer="flow.setAnswer"
        />
        <ProfileGenerationStage
          v-else-if="flow.currentStep.value"
          :active="flow.currentStep.value.kind === 'generation'"
          :summary="model.summary"
        />
      </div>

      <p
        v-if="submitBlocked"
        class="ob-submit-message"
        data-testid="onboarding-submit-message"
        role="alert"
      >
        {{ flow.submitMessage.value }}
      </p>
      <p v-else-if="!currentStepComplete" class="ob-validation" role="status">
        请先完成本页选择
      </p>

      <div class="ob-actions">
        <button
          v-if="!flow.isFirst.value"
          class="btn btn-ghost"
          type="button"
          data-action="onboarding-back"
          :disabled="submitting || !currentStepComplete"
          @click="flow.back"
        >
          上一步
        </button>
        <button
          class="btn btn-primary"
          type="button"
          data-action="onboarding-next"
          :disabled="submitting"
          @click="next"
        >
          {{ submitting ? '正在保存…' : nextLabel }}
        </button>
      </div>
      <button
        class="ob-skip"
        type="button"
        data-action="onboarding-skip"
        :disabled="submitting"
        @click="skip"
      >
        跳过，先随便看看
      </button>
      <p
        v-if="flow.isLast.value && model.state.mode === 'demo' && mismatchMessage"
        class="ob-skip"
        data-testid="questionnaire-contract-status"
      >
        {{ mismatchMessage }}
      </p>

      <div v-if="flow.isLast.value && model.consent.prompt" class="ob-consent" data-testid="onboarding-consent">
        <label class="ob-consent-row">
          <input
            type="checkbox"
            data-action="onboarding-consent"
            :checked="flow.consent.value"
            :disabled="submitting"
            @change="flow.setConsent(($event.target as HTMLInputElement).checked)"
          />
          <span>{{ model.consent.prompt }}</span>
        </label>
        <p class="ob-consent-note">{{ model.consent.note }}</p>
      </div>
    </div>
  </div>
</template>
