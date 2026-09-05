<script setup lang="ts">
import type { MemorySectionContract, UiMode } from '@/contracts'

import MemoryList from './MemoryList.vue'

defineProps<{
  model: MemorySectionContract
  removingIds?: ReadonlySet<string>
  mode?: UiMode
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()
</script>

<template>
  <div class="card p-card" data-profile-section="memory">
    <h3>
      <svg class="ic" aria-hidden="true"><use href="#i-book" /></svg>
      记忆小卡
      <span style="font-size:11px;color:var(--ink-3);font-weight:400">（点 × 撕掉）</span>
    </h3>
    <template v-if="model.status === 'available' && model.enabled">
      <MemoryList
        :items="model.items"
        :can-delete="model.canDelete"
        :removing-ids="removingIds"
        @remove="emit('remove', $event)"
      />
      <div class="consent">{{ model.notice }}</div>
      <div v-if="mode === 'demo'" class="consent" data-memory-local-only>
        演示模式：点击 × 只会移除当前页面里的示例，不会保存。
      </div>
    </template>
    <template v-else>
      <p class="consent" data-testid="memory-unavailable">
        {{ model.enabled ? model.unavailableMessage : '你还没有开启记忆功能。' }}
      </p>
    </template>
  </div>
</template>
