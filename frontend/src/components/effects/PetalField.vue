<script setup lang="ts">
import { onMounted, onUnmounted, shallowRef, useId } from 'vue'

import { useDecorativeField } from '@/composables/useDecorativeField'

/**
 * 花瓣飘落系统 — 迁移自 ui-prototypes/02-sakura-spring.html 的 petals() IIFE。
 *
 * 原型运动规律（逐项保留）：
 *   - 26 片花瓣，随机生成：深度 depth 决定尺寸(10~26px)/模糊(近景 0 / 远景 1.5px)/
 *     透明度(0.45~0.95) 与下落速度（越近越快 vy = 26 + depth*46）；
 *   - 初始即有约 2/3 花瓣落在视口内，其余从上方陆续飘入；
 *   - S 曲线横漂：sx = x + sin(t·freq + phase)·amp；
 *   - 呼吸式缩放：sc = scaleBase·(1 + 0.22·sin(t·freq·1.6 + phase))；
 *   - 自转：CSS petalSpin 关键帧（随机 5~11s 线性循环）+ 下落时的整体 rotate；
 *   - 生命周期：飘出视口底部(+60px)后从顶部(-60px)重生，横坐标重新随机。
 *
 * 工程化差异（仅实现方式，非视觉差异）：
 *   - 模板 v-for 渲染代替 createElement / appendChild；
 *   - RAF 循环来自 useDecorativeField（dt 钳制 0.05s 与原型一致），
 *     卸载自动停止；prefers-reduced-motion 时不启动循环（JS 侧降级）。
 */

/* 原型常量 */
const PETAL_COUNT = 26
const PETAL_COLORS: ReadonlyArray<readonly [string, string]> = [
  ['#ffd9e2', '#ffb7c5'],
  ['#fff0f4', '#ffd9e2'],
  ['#f3d9fa', '#e6c9f7'],
  ['#ffffff', '#ffd9e2'],
]

interface Petal {
  /* 视觉外观（静态） */
  size: number
  blur: number
  opacity: number
  colorFrom: string
  colorTo: string
  spinSeconds: number
  /* 运动状态（逐帧更新） */
  x: number
  y: number
  vy: number
  amp: number
  freq: number
  phase: number
  rot: number
  vr: number
  scaleBase: number
}

function createPetal(): Petal {
  const depth = Math.random() // 0 远 → 1 近
  const colors = PETAL_COLORS[Math.floor(Math.random() * PETAL_COLORS.length)]!
  return {
    size: 10 + depth * 16,
    blur: depth < 0.35 ? 1.5 : 0,
    opacity: 0.45 + depth * 0.5,
    colorFrom: colors[0],
    colorTo: colors[1],
    /* 原型 dur = (5 + Math.random() * 6).toFixed(1)：5.0~11.0 秒、保留一位小数 */
    spinSeconds: Number((5 + Math.random() * 6).toFixed(1)),
    x: Math.random() * window.innerWidth,
    /* 初始即有约 2/3 花瓣落在视口内，首屏立刻可见；其余从上方陆续飘入 */
    y: (Math.random() * 1.6 - 0.6) * window.innerHeight,
    vy: 26 + depth * 46, // 越近飘得越快
    amp: 30 + Math.random() * 55, // S 曲线摆幅
    freq: 0.4 + Math.random() * 0.8,
    phase: Math.random() * Math.PI * 2,
    rot: Math.random() * 360,
    vr: (Math.random() - 0.5) * 40,
    scaleBase: 0.75 + Math.random() * 0.5,
  }
}

const { reducedMotion, startLoop } = useDecorativeField()

const uid = useId()
/* 原型在脚本加载时生成整片花瓣；对应组件 setup 期生成，首帧渲染即完整 */
const petals = shallowRef<Petal[]>(Array.from({ length: PETAL_COUNT }, createPetal))
const petalEls: HTMLElement[] = []

let stopLoop: () => void = () => {}

function gradientId(index: number): string {
  return `pg-${uid}-${index}`
}

function setPetalEl(index: number, el: unknown): void {
  if (el instanceof HTMLElement) petalEls[index] = el
}

function paint(t: number): void {
  for (let i = 0; i < petals.value.length; i += 1) {
    const petal = petals.value[i]!
    const el = petalEls[i]
    if (!el) continue
    const sx = petal.x + Math.sin(t * petal.freq + petal.phase) * petal.amp // S 曲线横漂
    const sc = petal.scaleBase * (1 + 0.22 * Math.sin(t * petal.freq * 1.6 + petal.phase)) // 呼吸式缩放
    el.style.transform = `translate(${sx}px, ${petal.y}px) rotate(${petal.rot}deg) scale(${sc})`
  }
}

onMounted(() => {
  /* 首帧先就位（reduce 环境下也保留静态花瓣层，仅停止运动） */
  paint(performance.now() / 1000)
  if (!reducedMotion.value) {
    stopLoop = startLoop((deltaSeconds, elapsedSeconds) => {
      for (const petal of petals.value) {
        petal.y += petal.vy * deltaSeconds
        petal.rot += petal.vr * deltaSeconds
        if (petal.y > window.innerHeight + 60) {
          petal.y = -60
          petal.x = Math.random() * window.innerWidth
        }
      }
      paint(elapsedSeconds)
    })
  }
})

onUnmounted(() => {
  stopLoop()
  petalEls.length = 0
})
</script>

<template>
  <div id="petalField">
    <div
      v-for="(petal, index) in petals"
      :key="index"
      class="petal"
      :ref="el => setPetalEl(index, el)"
    >
      <svg
        :width="petal.size"
        :height="petal.size"
        viewBox="0 0 40 40"
        :style="{
          opacity: petal.opacity,
          filter: `blur(${petal.blur}px)`,
          animation: `petalSpin ${petal.spinSeconds}s linear infinite`,
        }"
      >
        <defs>
          <linearGradient :id="gradientId(index)" x1="0" y1="0" x2="40" y2="40">
            <stop offset="0" :stop-color="petal.colorFrom" />
            <stop offset="1" :stop-color="petal.colorTo" />
          </linearGradient>
        </defs>
        <path
          d="M20 2 C31 8 33 20 20 38 C7 20 9 8 20 2 Z"
          :fill="`url(#${gradientId(index)})`"
          opacity="0.9"
        />
      </svg>
    </div>
  </div>
</template>
