<script setup lang="ts">
import { computed, ref, useSlots } from 'vue'

import AppNavigation from '@/components/shell/AppNavigation.vue'
import DockedTaskProgress from '@/components/shell/DockedTaskProgress.vue'
import IconSprite from '@/components/shell/IconSprite.vue'
import PrototypeReplayControl from '@/components/shell/PrototypeReplayControl.vue'
import ToastHost from '@/components/shell/ToastHost.vue'
import { shellFixture } from '@/data/fixtures/shell.fixture'
import type { ShellContract, ViewId } from '@/contracts'

const emit = defineEmits<{
  replay: []
}>()

const props = withDefaults(
  defineProps<{
    shell?: ShellContract
  }>(),
  {
    shell: () => shellFixture,
  },
)

const slots = useSlots()
const activeView = ref<ViewId>('today')
const shell = computed(() => props.shell)
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
          <DockedTaskProgress :progress="shell.progress" />
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
      <PrototypeReplayControl @replay="emit('replay')" />
    </template>
    <slot v-else />
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

.view[style*='display: block'] {
  display: block;
  animation: shellViewIn 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes shellViewIn {
  from {
    opacity: 0;
    transform: translateY(22px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 560px) {
  .shell {
    padding: 24px 16px 90px;
  }
}
</style>
