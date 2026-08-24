<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useMotionPulse } from '@/composables/useMotionPulse'

const props = withDefaults(defineProps<{
  percentage: number
  replayKey?: number
}>(), {
  replayKey: 0,
})

const displayed = ref(0)
const eased = ref(0)
const { play, dispose } = useMotionPulse()

const strokeDashoffset = computed(() => String(258 * (1 - (props.percentage / 100) * eased.value)))

function animate(): void {
  dispose()
  displayed.value = 0
  eased.value = 0
  play(1500, (_, progress) => {
    eased.value = 1 - Math.exp(-4.5 * progress)
    displayed.value = Math.round(props.percentage * eased.value)
  })
}

watch(() => props.replayKey, animate)
watch(() => props.percentage, animate)

animate()
</script>

<template>
  <div class="ring-box" data-testid="completion-ring" :aria-label="`${props.percentage}% 完成率`">
    <svg viewBox="0 0 88 88" aria-hidden="true">
      <circle class="rbg" cx="44" cy="44" r="41" />
      <circle
        class="rfg"
        cx="44"
        cy="44"
        r="41"
        :style="{ strokeDashoffset }"
      />
    </svg>
    <div class="ring-num">{{ displayed }}%</div>
  </div>
</template>
