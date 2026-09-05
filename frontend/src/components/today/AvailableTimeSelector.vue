<script setup lang="ts">
import { ref } from 'vue'

import type { TodayTimeOption } from '@/contracts'
import { useMotionPulse } from '@/composables/useMotionPulse'

/**
 * 冻结原型 .mood-card 下半部（910-918 行）：课后可用时间三枚 chip。
 * 点击单选切换 .on，并做原型 scale(1+0.09v) 650ms 脉冲。
 */
defineProps<{
  options: readonly TodayTimeOption[]
  selectedMinutes: number
}>()

const emit = defineEmits<{
  select: [minutes: number]
}>()

const { play } = useMotionPulse()
const pulseMinutes = ref<number | null>(null)
const pulseTransform = ref('')

function onSelect(minutes: number): void {
  pulseMinutes.value = minutes
  play(
    650,
    v => {
      pulseTransform.value = `scale(${1 + 0.09 * v})`
    },
    () => {
      pulseTransform.value = ''
      pulseMinutes.value = null
    },
  )
  emit('select', minutes)
}
</script>

<template>
  <div class="mood-row">
    <div class="lbl">课后可用时间</div>
    <div class="chips">
      <button
        v-for="option in options"
        :key="option.minutes"
        class="chip"
        :class="{ on: option.minutes === selectedMinutes }"
        type="button"
        :aria-pressed="option.minutes === selectedMinutes"
        :style="option.minutes === pulseMinutes ? { transform: pulseTransform } : undefined"
        @click="onSelect(option.minutes)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>
