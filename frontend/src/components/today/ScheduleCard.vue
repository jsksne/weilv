<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { UiDataSource } from '@/contracts'
import type { ScheduleEventContract, ScheduleEventUpsertContract } from '@/contracts/common'
import { useToast } from '@/composables/useToast'

/**
 * 日程最小实现：首页只简短呈现当天安排；详细增删改在这里完成。
 * 名称是用户数据，只用于展示——不会进入任何推荐提示词。
 */
const props = defineProps<{
  dataSource?: UiDataSource
}>()

const { push } = useToast()

const events = ref<ScheduleEventContract[]>([])
const loading = ref(false)
const expanded = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)

const KIND_LABELS: Record<string, string> = {
  exam: '考试',
  holiday: '假期',
  plan: '安排',
}
const BUSY_LABELS: Record<string, string> = {
  busy: '很忙',
  some: '一般忙',
  free: '比较空',
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

const form = ref<ScheduleEventUpsertContract>({
  name: '',
  start_date: todayIso(),
  end_date: todayIso(),
  kind: 'plan',
  busy_level: null,
})

/** 当天(或跨天包含今天)生效的事件。 */
const todayEvents = computed(() =>
  events.value.filter(event => event.start_date <= todayIso() && event.end_date >= todayIso()),
)

const summary = computed(() => {
  if (todayEvents.value.length === 0) return '今天没有日程安排'
  return `今天：${todayEvents.value
    .slice(0, 3)
    .map(event => `${event.name}（${KIND_LABELS[event.kind] ?? event.kind}）`)
    .join(' · ')}`
})

async function reload(): Promise<void> {
  if (!props.dataSource?.getSchedule) return
  loading.value = true
  try {
    events.value = await props.dataSource.getSchedule()
  } catch {
    push('日程暂时读不到，稍后再试')
  } finally {
    loading.value = false
  }
}

onMounted(reload)

function startCreate(): void {
  editingId.value = null
  form.value = { name: '', start_date: todayIso(), end_date: todayIso(), kind: 'plan', busy_level: null }
}

function startEdit(event: ScheduleEventContract): void {
  editingId.value = event.event_id
  form.value = {
    name: event.name,
    start_date: event.start_date,
    end_date: event.end_date,
    kind: event.kind,
    busy_level: event.busy_level,
  }
}

async function save(): Promise<void> {
  if (!form.value.name.trim() || saving.value) return
  saving.value = true
  try {
    const result = await props.dataSource?.saveScheduleEvent?.(
      { ...form.value, name: form.value.name.trim() },
      editingId.value ?? undefined,
    )
    if (result?.status === 'saved') {
      push(editingId.value ? '日程已更新' : '日程已记下')
      await reload()
      startCreate()
    } else {
      push('没有保存成功，请重试')
    }
  } catch {
    push('没有保存成功，请重试')
  } finally {
    saving.value = false
  }
}

async function remove(event: ScheduleEventContract): Promise<void> {
  try {
    const result = await props.dataSource?.deleteScheduleEvent?.(event.event_id)
    if (result?.status === 'deleted') {
      push('已删除')
      await reload()
    }
  } catch {
    push('删除没有成功，请重试')
  }
}

function busyLabel(level: string | null): string {
  return level ? BUSY_LABELS[level] ?? '' : ''
}
</script>

<template>
  <div class="card schedule-card" data-testid="schedule-card">
    <div class="schedule-head">
      <span class="schedule-ic" aria-hidden="true">🗓</span>
      <p class="schedule-summary">{{ summary }}</p>
      <button class="btn btn-ghost" type="button" data-testid="schedule-toggle" @click="expanded = !expanded">
        {{ expanded ? '收起' : '记一笔' }}
      </button>
    </div>

    <div v-if="expanded" class="schedule-body">
      <ul v-if="events.length > 0" class="schedule-list">
        <li v-for="event in events" :key="event.event_id" class="schedule-item">
          <div>
            <b>{{ event.name }}</b>
            <span class="schedule-meta">
              {{ event.start_date }} ~ {{ event.end_date }} · {{ KIND_LABELS[event.kind] ?? event.kind }}
              <template v-if="event.busy_level"> · {{ busyLabel(event.busy_level) }}</template>
            </span>
          </div>
          <div class="schedule-item-actions">
            <button class="btn btn-ghost" type="button" :data-action="`schedule-edit-${event.event_id}`" @click="startEdit(event)">修改</button>
            <button class="btn btn-ghost" type="button" :data-action="`schedule-delete-${event.event_id}`" @click="remove(event)">删除</button>
          </div>
        </li>
      </ul>
      <p v-else class="schedule-empty">还没有日程。记录考试或假期，推荐会更懂你的节奏。</p>

      <form class="schedule-form" @submit.prevent="save">
        <input
          v-model="form.name"
          data-testid="schedule-name"
          type="text"
          placeholder="比如：数学期中考试 / 周末放假"
          aria-label="日程名称"
          maxlength="60"
        />
        <div class="schedule-row">
          <label>开始 <input v-model="form.start_date" type="date" data-testid="schedule-start" /></label>
          <label>结束 <input v-model="form.end_date" type="date" data-testid="schedule-end" /></label>
        </div>
        <div class="schedule-row">
          <label>
            类型
            <select v-model="form.kind" data-testid="schedule-kind">
              <option value="exam">考试</option>
              <option value="holiday">假期</option>
              <option value="plan">普通安排</option>
            </select>
          </label>
          <label>
            忙碌程度（可选）
            <select v-model="form.busy_level" data-testid="schedule-busy">
              <option :value="null">不填</option>
              <option value="busy">很忙</option>
              <option value="some">一般忙</option>
              <option value="free">比较空</option>
            </select>
          </label>
        </div>
        <div class="schedule-form-actions">
          <button class="btn btn-primary" type="submit" data-testid="schedule-save" :disabled="saving">
            {{ editingId ? '保存修改' : '记下' }}
          </button>
          <button v-if="editingId" class="btn btn-ghost" type="button" @click="startCreate">取消</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.schedule-card {
  padding: 14px 16px;
}

.schedule-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.schedule-ic {
  font-size: 18px;
}

.schedule-summary {
  flex: 1;
  margin: 0;
  font-size: 13px;
  color: var(--ink-1, #3f3348);
}

.schedule-body {
  margin-top: 12px;
  border-top: 1px dashed rgba(247, 143, 176, 0.4);
  padding-top: 12px;
}

.schedule-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: grid;
  gap: 8px;
}

.schedule-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}

.schedule-meta {
  display: block;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.schedule-item-actions {
  display: flex;
  gap: 4px;
}

.schedule-empty {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.schedule-form {
  display: grid;
  gap: 8px;
}

.schedule-form input[type='text'] {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid rgba(247, 143, 176, 0.42);
  border-radius: 12px;
  font: inherit;
}

.schedule-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--ink-2, #7c6f86);
}

.schedule-row select,
.schedule-row input {
  font: inherit;
  border: 1px solid rgba(247, 143, 176, 0.42);
  border-radius: 10px;
  padding: 4px 6px;
}

.schedule-form-actions {
  display: flex;
  gap: 8px;
}
</style>
