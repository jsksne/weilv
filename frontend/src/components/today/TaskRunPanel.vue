<script setup lang="ts">
import { watch } from 'vue'

import type { DailyTaskEntry } from '@/composables/useDailyTasks'

/**
 * F3：任务进行中界面。复用今日/AI 两个入口的同一执行记录；
 * 关闭面板不结束任务；「先放下」保留可恢复状态（与跳过共用 restore 语义）。
 */
const props = defineProps<{
  entry: DailyTaskEntry
  submitting: boolean
}>()

const emit = defineEmits<{
  close: []
  done: []
  partial: []
  pause: []
}>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

watch(
  () => props.entry,
  () => undefined,
)
</script>

<template>
  <div class="run-mask" data-testid="task-run-panel" role="dialog" aria-modal="true" :aria-label="`正在做：${entry.task.name}`" @click.self="emit('close')">
    <div class="run-card card" tabindex="-1" @keydown="onKeydown">
      <div class="run-top">
        <span class="task-domain">{{ entry.task.domain }}</span>
        <span class="task-meta">{{ entry.task.meta }}</span>
      </div>
      <h3 class="run-name">{{ entry.task.name }}</h3>
      <p class="run-steps">{{ entry.task.description }}</p>
      <div class="run-why">
        <span class="why-icon" aria-hidden="true">❀</span>
        <p>{{ entry.task.why }}</p>
      </div>
      <p class="run-note">关闭这里不会结束任务，随时可以回来继续。</p>
      <div class="run-actions">
        <button class="btn btn-ok" type="button" data-act="panel-done" :disabled="submitting" @click="emit('done')">
          ✓ 完成了
        </button>
        <button class="btn btn-ghost" type="button" data-act="panel-partial" :disabled="submitting" @click="emit('partial')">
          做了一部分
        </button>
        <button class="btn btn-ghost" type="button" data-act="panel-pause" :disabled="submitting" @click="emit('pause')">
          先放下
        </button>
        <button class="btn btn-ghost" type="button" data-act="panel-close" @click="emit('close')">
          先收起来
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.run-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(72, 46, 84, 0.35);
  backdrop-filter: blur(3px);
}

.run-card {
  width: min(420px, 100%);
  padding: 22px 20px;
  border-radius: 22px;
  background: rgba(255, 250, 252, 0.98);
  box-shadow: 0 18px 48px rgba(110, 74, 118, 0.28);
  animation: runIn 0.28s var(--ease-decay, ease-out) both;
}

@keyframes runIn {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
}

.run-top {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.run-name {
  margin: 10px 0 6px;
  font-size: 19px;
  color: var(--ink-1, #3f3348);
}

.run-steps {
  margin: 0 0 12px;
  line-height: 1.7;
  color: var(--ink-1, #3f3348);
}

.run-why {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(247, 143, 176, 0.12);
  font-size: 13px;
  color: var(--ink-2, #7c6f86);
}

.run-why p {
  margin: 0;
}

.run-note {
  margin: 0 0 14px;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.run-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
