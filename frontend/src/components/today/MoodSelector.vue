<script setup lang="ts">
import { ref } from 'vue'

import type { TodayMoodOption } from '@/contracts'
import { useMotionPulse } from '@/composables/useMotionPulse'

/**
 * 冻结原型 .mood-card 上半部（900-909 行）：心情头与四个心情钮。
 * 点击单选切换 .on，并对所点按钮做原型 scale(1+0.1v) rotate(-3v)
 * 700ms 脉冲；「有点低落」的换卡语义由 controller 处理。
 */
defineProps<{
  moods: readonly TodayMoodOption[]
  selected: string
}>()

const emit = defineEmits<{
  select: [value: string]
}>()

const { play } = useMotionPulse()
const pulseValue = ref<string | null>(null)
const pulseTransform = ref('')

function onSelect(value: string): void {
  pulseValue.value = value
  play(
    700,
    v => {
      pulseTransform.value = `scale(${1 + 0.1 * v}) rotate(${-3 * v}deg)`
    },
    () => {
      pulseTransform.value = ''
      pulseValue.value = null
    },
  )
  emit('select', value)
}
</script>

<template>
  <div class="mood-head">
    <h3>此刻的你，感觉怎么样？</h3>
    <span class="live"><i></i>随时可改</span>
  </div>
  <div class="mood-row">
    <div class="moods">
      <button
        v-for="option in moods"
        :key="option.value"
        class="mood"
        :class="{ on: option.value === selected }"
        type="button"
        :aria-pressed="option.value === selected"
        :style="option.value === pulseValue ? { transform: pulseTransform } : undefined"
        @click="onSelect(option.value)"
      >
        <span class="face">{{ option.face }}</span>
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>
