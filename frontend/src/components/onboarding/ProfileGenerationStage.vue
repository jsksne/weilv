<script setup lang="ts">
import { ref, watch } from 'vue'

import { useMotionPulse } from '@/composables/useMotionPulse'
import type { OnboardingSummaryContract } from '@/contracts'

const props = defineProps<{
  active: boolean
  summary: OnboardingSummaryContract
}>()

const emit = defineEmits<{
  generated: []
}>()

const coreOpacity = ref(0)
const coreScale = ref(0.6)
const ringOpacity = ref(0)
const text = ref('正在汇聚你的回答…')
const generated = ref(false)
const { play, delay, dispose } = useMotionPulse()

function reset(): void {
  dispose()
  coreOpacity.value = 0
  coreScale.value = 0.6
  ringOpacity.value = 0
  text.value = '正在汇聚你的回答…'
  generated.value = false
}

function start(): void {
  reset()
  play(900, (_, progress) => {
    const eased = 1 - Math.exp(-4.2 * progress)
    coreOpacity.value = Math.min(1, progress * 3)
    coreScale.value = 0.6 + 0.4 * eased
    ringOpacity.value = Math.min(1, progress * 2.5)
  }, () => {
    text.value = '正在匹配审核任务白名单…'
    delay(1000, () => {
      generated.value = true
      text.value = '初始画像已生成'
      emit('generated')
    })
  })
}

watch(() => props.active, active => {
  if (active) start()
  else reset()
}, { immediate: true })
</script>

<template>
  <div v-if="props.active" class="ob-step active" data-onboarding-step="generation">
    <h2>生成初始画像</h2>
    <div class="gen-stage">
      <div class="gen-ring" :style="{ opacity: ringOpacity }" />
      <div
        class="gen-core"
        :style="{ opacity: coreOpacity, transform: `scale(${coreScale})` }"
      >
        <span v-if="generated">✦</span>
      </div>
    </div>
    <p class="gen-txt">{{ text }}</p>
    <div v-if="generated" class="ob-summary">
      <b>{{ props.summary.title }}</b>
      <p>
        <template v-for="(line, index) in props.summary.lines" :key="line">
          {{ line }}<br v-if="index < props.summary.lines.length - 1" />
        </template>
      </p>
    </div>
  </div>
</template>
