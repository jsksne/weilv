<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue'

import type { TodayContract } from '@/contracts'
import { useMotionPulse } from '@/composables/useMotionPulse'
import AvailableTimeSelector from './AvailableTimeSelector.vue'
import MoodSelector from './MoodSelector.vue'

/**
 * 冻结原型「现在的心情」区块（899-919 行）：section-title + .card.mood-card。
 * 组件化只改变代码组织：section 标题、心情选择、时间选择、已计入说明
 * 的 DOM 结构与类名逐字保留。
 *
 * defineExpose(focusCheck)：对应原型 btnCheck 的滚动聚焦——
 * scrollIntoView(center) + check-focus 1.6s 光晕（1700ms 后移除；
 * 先移除类再于 nextTick 加回，等价原型 remove→reflow→add 的动画重播）。
 */
defineProps<{
  model: TodayContract
  mood: string
  availableMinutes: number
}>()

const emit = defineEmits<{
  'select-mood': [value: string]
  'select-time': [minutes: number]
}>()

const card = ref<HTMLElement | null>(null)
const focusing = ref(false)
const { delay, dispose } = useMotionPulse()

function focusCheck(): void {
  card.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  focusing.value = false
  void nextTick(() => {
    focusing.value = true
    delay(1700, () => {
      focusing.value = false
    })
  })
}

onUnmounted(dispose)

defineExpose({ focusCheck })
</script>

<template>
  <div class="section-title">
    <h2>现在的心情</h2>
    <span>心情会轻轻影响推荐</span>
  </div>
  <div ref="card" class="card mood-card" :class="{ 'check-focus': focusing }">
    <MoodSelector :moods="model.moods" :selected="mood" @select="emit('select-mood', $event)" />
    <AvailableTimeSelector
      :options="model.timeOptions"
      :selected-minutes="availableMinutes"
      @select="emit('select-time', $event)"
    />
    <div class="mood-note">
      <b>{{ model.moodNoteLead }}</b>{{ model.moodNoteLines[0] }}<br />{{ model.moodNoteLines[1] }}
    </div>
  </div>
</template>
