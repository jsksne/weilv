<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, push, dismiss, clear } = useToast()

defineExpose({ toasts, push, dismiss, clear })
</script>

<template>
  <div id="toastBox" class="toast-box" data-testid="toast-host" aria-live="polite">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast"
      :class="{ out: toast.leaving }"
    >
      {{ toast.message }}
    </div>
  </div>
</template>
