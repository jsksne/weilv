<script setup lang="ts">
defineProps<{
  displayName: string
  tagline: string
}>()

const emit = defineEmits<{
  activate: []
}>()
</script>

<template>
  <div
    class="logo"
    role="button"
    tabindex="0"
    :aria-label="displayName"
    @click="emit('activate')"
    @keydown.enter="emit('activate')"
    @keydown.space.prevent="emit('activate')"
  >
    <svg class="logo-flower" viewBox="0 0 32 32">
      <g fill="none">
        <path d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z" fill="#ffb7c5" />
        <path
          d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z"
          fill="#ffd9e2"
          transform="rotate(72 16 16)"
        />
        <path
          d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z"
          fill="#ffb7c5"
          transform="rotate(144 16 16)"
        />
        <path
          d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z"
          fill="#e6c9f7"
          transform="rotate(216 16 16)"
        />
        <path
          d="M16 4 C19 8 19 12 16 15 C13 12 13 8 16 4 Z"
          fill="#ffd9e2"
          transform="rotate(288 16 16)"
        />
        <circle cx="16" cy="16" r="3" fill="#f78fb0" />
      </g>
    </svg>
    <div><b>微律</b><span>{{ tagline }}</span></div>
  </div>
</template>

<style scoped>
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.logo-flower {
  width: 30px;
  height: 30px;
  animation: flowerSway 6s ease-in-out infinite;
  transform-origin: 50% 80%;
}

.logo b {
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', serif;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #f27ba4;
}

.logo span {
  font-size: 10px;
  color: #9b8495;
  letter-spacing: 2px;
  display: block;
  margin-top: 1px;
}

@keyframes flowerSway {
  0%,
  100% {
    transform: rotate(-6deg);
  }

  50% {
    transform: rotate(8deg);
  }
}
</style>
