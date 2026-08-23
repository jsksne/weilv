<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'

import { useMotionPulse, type MotionPulse } from '@/composables/useMotionPulse'

/**
 * 任务完成特效 — 迁移自 ui-prototypes/02-sakura-spring.html 的
 * convergeFx / orbFx / haloFx / taskCompleteFx。
 *
 * 时序与参数逐项保留：
 *   1. 粒子汇聚：16 粒，dur 640ms + i·16ms 逐粒错峰；
 *      磁吸式缓动 e = 1 - exp(-4.2t)（先快后慢），透明度 min(1, t·3)；
 *   2. 核心光球：+620ms 触发，1150ms，scale = 0.4 + 1.05·pulse(v)，
 *      opacity = min(1, t·5) · max(0.25, v)；
 *   3. 光环扩散：+780ms 触发，950ms，scale = 0.6 + 2.2t，opacity = 0.5(1-t)。
 *
 * 工程化差异（仅实现方式，非视觉差异）：
 *   - 原型把 fx 元素 append 到 document.body 并手动 remove；
 *     本组件以 fixed 定位的响应式元素渲染（CSS 见 styles/effects.css，
 *     z-index 95/96/97 与原型一致），状态由 ref 驱动；
 *   - 所有 RAF / timeout 经 useMotionPulse 登记，组件卸载自动清理；
 *   - prefers-reduced-motion 时 play() 直接跳过（JS 侧主动降级）；
 *     播放途中切换到 reduce 也会立即取消并复位（FUTURE-S3-01）。
 */

const emit = defineEmits<{
  /** 三段特效全部结束后触发一次（reduce 环境跳过特效时不触发） */
  done: []
}>()

/* 原型常量 */
const FX_COLORS = ['#ffb7c5', '#f78fb0', '#c9a8eb', '#9d7bdf', '#7cc6b7', '#ffc4a3']
const PARTICLE_COUNT = 16
const CONVERGE_DURATION_MS = 640
const CONVERGE_STAGGER_MS = 16
const ORB_DELAY_MS = 620
const ORB_DURATION_MS = 1150
const HALO_DELAY_MS = 780
const HALO_DURATION_MS = 950

interface FxParticle {
  id: number
  left: number
  top: number
  size: number
  color: string
  boxShadow: string
  transform: string
  opacity: number
}

const pulse: MotionPulse = useMotionPulse()
const { reducedMotion, play, nextFrame, delay, dispose } = pulse

const particles = ref<FxParticle[]>([])
const orb = ref({ visible: false, left: 0, top: 0, transform: '', opacity: 1 })
const halo = ref({ visible: false, left: 0, top: 0, transform: '', opacity: 1 })

let particleSeq = 0
let running = false

function finishIfSettled(particlesDone: boolean, orbDone: boolean, haloDone: boolean): void {
  if (particlesDone && orbDone && haloDone && running) {
    running = false
    emit('done')
  }
}

/**
 * 在视口坐标 (cx, cy) 处播放完整特效。
 * 与原型 taskCompleteFx(card) 等价——坐标由调用方（任务卡 .task-state
 * 的 getBoundingClientRect 中心）在 Sprint 3 接入视图时传入。
 */
function playCompletion(cx: number, cy: number): void {
  if (reducedMotion.value || running) return
  running = true

  /* 1. 粒子汇聚 */
  const spawned: Array<{ particle: FxParticle; sx: number; sy: number }> = []
  let particlesDone = false
  let orbDone = false
  let haloDone = false

  for (let i = 0; i < PARTICLE_COUNT; i += 1) {
    const size = 4 + Math.random() * 5
    const color = FX_COLORS[i % FX_COLORS.length]!
    const angle = (Math.PI * 2 * i) / PARTICLE_COUNT + Math.random() * 0.8
    const distance = 74 + Math.random() * 92
    const sx = Math.cos(angle) * distance
    const sy = Math.sin(angle) * distance
    const particle: FxParticle = {
      id: (particleSeq += 1),
      left: cx - size / 2,
      top: cy - size / 2,
      size,
      color,
      boxShadow: `0 0 ${size * 2.6}px ${color}`,
      transform: `translate(${sx}px, ${sy}px) scale(0.5)`,
      opacity: 0,
    }
    particles.value.push(particle)
    spawned.push({ particle, sx, sy })
  }

  /* 原型用双层 rAF 等首帧布局后再起播，此处保持一致 */
  nextFrame(() =>
    nextFrame(() => {
      let doneCount = 0
      spawned.forEach(({ particle, sx, sy }, index) => {
        play(
          CONVERGE_DURATION_MS + index * CONVERGE_STAGGER_MS,
          (_value, t) => {
            const e = 1 - Math.exp(-4.2 * t) // 磁吸式先快后慢
            particle.transform = `translate(${sx * (1 - e)}px, ${sy * (1 - e)}px) scale(${0.5 + 0.6 * e})`
            particle.opacity = Math.min(1, t * 3)
          },
          () => {
            particles.value = particles.value.filter(item => item.id !== particle.id)
            doneCount += 1
            if (doneCount === spawned.length) {
              particlesDone = true
              finishIfSettled(particlesDone, orbDone, haloDone)
            }
          },
        )
      })
    }),
  )

  /* 2. 核心光球（吸收 → 脉冲 → 消散，符号随后浮现） */
  delay(ORB_DELAY_MS, () => {
    orb.value = { visible: true, left: cx, top: cy, transform: 'translate(-50%, -50%) scale(0.4)', opacity: 0 }
    play(
      ORB_DURATION_MS,
      (value, t) => {
        orb.value.transform = `translate(-50%, -50%) scale(${0.4 + 1.05 * value})`
        orb.value.opacity = Math.min(1, t * 5) * Math.max(0.25, value)
      },
      () => {
        orb.value.visible = false
        orbDone = true
        finishIfSettled(particlesDone, orbDone, haloDone)
      },
    )
  })

  /* 3. 光环扩散 */
  delay(HALO_DELAY_MS, () => {
    halo.value = { visible: true, left: cx, top: cy, transform: 'translate(-50%, -50%) scale(0.6)', opacity: 0.5 }
    play(
      HALO_DURATION_MS,
      (_value, t) => {
        halo.value.transform = `translate(-50%, -50%) scale(${0.6 + 2.2 * t})`
        halo.value.opacity = 0.5 * (1 - t)
      },
      () => {
        halo.value.visible = false
        haloDone = true
        finishIfSettled(particlesDone, orbDone, haloDone)
      },
    )
  })
}

function reset(): void {
  particles.value = []
  orb.value.visible = false
  halo.value.visible = false
  running = false
}

/* FUTURE-S3-01：播放途中系统切到 prefers-reduced-motion 时，useMotionPulse
   已取消全部 RAF/timer，但瞬态 FX 状态与 running 必须同步复位，
   否则组件永久卡在 running、特效 DOM 残留；复位后恢复 motion 仍可再次 play() */
watch(reducedMotion, reduced => {
  if (reduced && running) {
    dispose()
    reset()
  }
})

onUnmounted(() => {
  dispose()
  reset()
})

defineExpose({ play: playCompletion, reset })
</script>

<template>
  <span
    v-for="particle in particles"
    :key="particle.id"
    class="fx-p"
    aria-hidden="true"
    :style="{
      left: `${particle.left}px`,
      top: `${particle.top}px`,
      width: `${particle.size}px`,
      height: `${particle.size}px`,
      background: particle.color,
      boxShadow: particle.boxShadow,
      transform: particle.transform,
      opacity: particle.opacity,
    }"
  ></span>
  <span
    v-if="orb.visible"
    class="fx-orb"
    aria-hidden="true"
    :style="{ left: `${orb.left}px`, top: `${orb.top}px`, transform: orb.transform, opacity: orb.opacity }"
  ></span>
  <span
    v-if="halo.visible"
    class="fx-halo"
    aria-hidden="true"
    :style="{ left: `${halo.left}px`, top: `${halo.top}px`, transform: halo.transform, opacity: halo.opacity }"
  ></span>
</template>
