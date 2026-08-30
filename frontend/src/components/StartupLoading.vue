<script setup lang="ts">
import type { UiLoadProgress } from '@/composables/useUiDataSource'

defineProps<{
  progress: UiLoadProgress
}>()
</script>

<template>
  <section class="startup-loading" data-testid="ui-data-loading" role="status" aria-live="polite">
    <div class="startup-card">
      <div class="startup-orbit" aria-hidden="true">
        <div class="startup-ring" />
        <svg class="startup-flower" viewBox="0 0 32 32">
          <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#ffb7c5" />
          <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#ffd9e2" transform="rotate(72 16 16)" />
          <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#ffb7c5" transform="rotate(144 16 16)" />
          <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#e6c9f7" transform="rotate(216 16 16)" />
          <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#ffd9e2" transform="rotate(288 16 16)" />
          <circle cx="16" cy="16" r="3" fill="#f78fb0" />
        </svg>
      </div>
      <p class="startup-kicker">正在为你准备微律</p>
      <h1>{{ progress.stage }}</h1>
      <div
        class="startup-track"
        role="progressbar"
        aria-label="微律数据加载进度"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="progress.percent"
      >
        <span :style="{ width: `${progress.percent}%` }" />
      </div>
      <div class="startup-meta">
        <span>{{ progress.completed }} / {{ progress.total }}</span>
        <strong>{{ progress.percent }}%</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
.startup-loading {
  position: relative;
  z-index: 10;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.startup-card {
  width: min(390px, 100%);
  padding: 34px 32px 30px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.88);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 24px 70px rgba(143, 111, 208, 0.15);
  backdrop-filter: blur(18px);
}

.startup-orbit {
  position: relative;
  width: 104px;
  height: 104px;
  margin: 0 auto 20px;
  display: grid;
  place-items: center;
}

.startup-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 0deg, #ffb7c5, #ffc4a3, #c9a8eb, #7cc6b7, #ffb7c5);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 3px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 3px));
  animation: startup-spin 2.6s linear infinite;
}

.startup-flower {
  width: 58px;
  filter: drop-shadow(0 8px 16px rgba(247, 143, 176, 0.25));
  animation: startup-breathe 2.2s ease-in-out infinite;
}

.startup-kicker {
  margin: 0 0 8px;
  color: var(--pink-deep);
  font-size: 12px;
  letter-spacing: 2px;
}

h1 {
  margin: 0 0 24px;
  color: var(--ink);
  font: 600 24px/1.4 var(--disp);
  letter-spacing: 1px;
}

.startup-track {
  height: 7px;
  overflow: hidden;
  border-radius: 99px;
  background: rgba(147, 113, 138, 0.12);
}

.startup-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--grad-aurora);
  box-shadow: 0 0 16px rgba(233, 160, 220, 0.45);
  transition: width 0.55s var(--ease-decay);
}

.startup-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  color: var(--ink-3);
  font-size: 12px;
}

.startup-meta strong { color: var(--purple-deep); }

@keyframes startup-spin { to { transform: rotate(360deg); } }
@keyframes startup-breathe { 50% { transform: scale(1.08) rotate(2deg); } }

@media (prefers-reduced-motion: reduce) {
  .startup-ring,
  .startup-flower { animation: none; }
  .startup-track span { transition: none; }
}
</style>
