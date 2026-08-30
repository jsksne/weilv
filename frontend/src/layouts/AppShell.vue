<script setup lang="ts">
import { computed, ref, useSlots } from 'vue'

import AppNavigation from '@/components/shell/AppNavigation.vue'
import IconSprite from '@/components/shell/IconSprite.vue'
import PrototypeReplayControl from '@/components/shell/PrototypeReplayControl.vue'
import TourReplayControl from '@/components/shell/TourReplayControl.vue'
import ToastHost from '@/components/shell/ToastHost.vue'
import AuroraBackground from '@/components/effects/AuroraBackground.vue'
import type { ShellContract, ViewId } from '@/contracts'

const emit = defineEmits<{
  replay: []
  tour: []
}>()

const unavailableShell: ShellContract = {
  state: { status: 'unavailable', mode: 'production' },
  navigation: [],
  displayName: '',
  dateLabel: '',
  progress: { completed: 0, total: 0, note: '' },
  toastExample: { id: 'unavailable-shell', message: '' },
}

const props = defineProps<{
  shell?: ShellContract
}>()

const slots = useSlots()
const activeView = ref<ViewId>('today')
const shell = computed(() => props.shell ?? unavailableShell)
const shellMode = computed(() =>
  (['today', 'assistant', 'profile', 'weekly'] as const).some(view => Boolean(slots[view])),
)

function switchView(view: ViewId): void {
  activeView.value = view
  if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

defineExpose({ activeView, shell: props.shell, switchView })
</script>

<template>
  <div class="weilv-app-shell" :class="{ 'weilv-shell-root': shellMode }">
    <AuroraBackground />
    <template v-if="shellMode">
      <IconSprite />
      <AppNavigation
        :items="shell.navigation"
        :display-name="shell.displayName"
        :date-label="shell.dateLabel"
        :active-view="activeView"
        @update:active-view="switchView"
      />
      <main class="shell" data-shell-container>
        <section
          id="view-today"
          v-show="activeView === 'today'"
          class="view"
          :class="{ active: activeView === 'today' }"
          data-view="today"
        >
          <slot name="today" />
        </section>
        <section
          id="view-assistant"
          v-show="activeView === 'assistant'"
          class="view"
          :class="{ active: activeView === 'assistant' }"
          data-view="assistant"
        >
          <slot name="assistant" />
        </section>
        <section
          id="view-profile"
          v-show="activeView === 'profile'"
          class="view"
          :class="{ active: activeView === 'profile' }"
          data-view="profile"
        >
          <slot name="profile" />
        </section>
        <section
          id="view-weekly"
          v-show="activeView === 'weekly'"
          class="view"
          :class="{ active: activeView === 'weekly' }"
          data-view="weekly"
        >
          <slot name="weekly" />
        </section>
      </main>
      <ToastHost />
      <TourReplayControl @tour="emit('tour')" />
      <PrototypeReplayControl @replay="emit('replay')" />
    </template>
    <!-- legacy 内容为静态流式布局；包装层保证其位于 .bg（z-index 0）之上，
         与冻结原型 .shell 的内容层级约定一致，不改变 legacy 自身布局 -->
    <div v-else class="shell-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  z-index: 1;
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 22px 110px;
}

.view {
  display: none;
}

.view.active {
  display: block;
}

.shell-content {
  position: relative;
  z-index: 1;
}

@media (max-width: 560px) {
  .shell {
    padding: 24px 16px 90px;
  }
}
</style>
