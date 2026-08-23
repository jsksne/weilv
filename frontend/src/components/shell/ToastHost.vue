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

<style scoped>
.toast-box {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 90;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  pointer-events: none;
}

.toast {
  padding: 12px 24px;
  border-radius: 999px;
  font-size: 13px;
  letter-spacing: 1px;
  color: #594452;
  background: rgba(255, 255, 255, 0.95);
  border: 1.5px solid rgba(255, 183, 197, 0.7);
  box-shadow: 0 12px 36px rgba(247, 143, 176, 0.25);
  animation: toastIn 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
  display: flex;
  gap: 8px;
  align-items: center;
}

.toast.out {
  animation: toastOut 0.5s cubic-bezier(0.55, 0.055, 0.675, 0.19) forwards;
}

@keyframes toastIn {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.9);
  }

  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes toastOut {
  to {
    opacity: 0;
    transform: translateY(12px) scale(0.94);
  }
}
</style>
