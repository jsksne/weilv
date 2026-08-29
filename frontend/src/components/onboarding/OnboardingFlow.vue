<script setup lang="ts">
import { computed, ref, watch } from 'vue'

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

watch(() => props.open, value => {
  open.value = value
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
    open.value = false
  })
}

async function next(): Promise<void> {
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
    class="onboard"
    :class="{ hide: closing }"
    data-testid="onboarding"
    role="dialog"
    aria-modal="true"
    aria-label="首次使用引导"
  >
    <div class="ob-card">
      <OnboardingProgress :current="currentNumber" :total="flow.total.value" />

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

      <div v-if="flow.isLast && model.consent.prompt" class="ob-consent" data-testid="onboarding-consent">
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

      <p
        v-if="submitBlocked"
        class="ob-submit-message"
        data-testid="onboarding-submit-message"
        role="alert"
      >
        {{ flow.submitMessage.value }}
      </p>

      <div class="ob-actions">
        <button
          v-if="!flow.isFirst.value"
          class="btn btn-ghost"
          type="button"
          data-action="onboarding-back"
          :disabled="submitting"
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
        v-if="model.state.mode === 'demo' && mismatchMessage"
        class="ob-skip"
        data-testid="questionnaire-contract-status"
      >
        {{ mismatchMessage }}
      </p>
    </div>
  </div>
</template>
