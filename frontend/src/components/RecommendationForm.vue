<script setup lang="ts">
import type { RecommendationRequest } from '@/api/types'

const props = defineProps<{
  form: RecommendationRequest
  loading: boolean
}>()

defineEmits<{
  change: [field: keyof RecommendationRequest, value: RecommendationRequest[keyof RecommendationRequest]]
  submit: []
  reset: []
}>()

function textValue(event: Event): string {
  return (event.target as HTMLInputElement).value
}

function numberValue(event: Event): number {
  return Number((event.target as HTMLInputElement).value)
}

function checkedValue(event: Event): boolean {
  return (event.target as HTMLInputElement).checked
}
</script>

<template>
  <form @submit.prevent="$emit('submit')">
    <h2>当前状态</h2>

    <label>
      演示用户 ID
      <input
        :value="props.form.user_id"
        name="user_id"
        required
        @input="$emit('change', 'user_id', textValue($event).trim())"
      />
    </label>

    <label>
      当前状态描述
      <textarea
        :value="props.form.query"
        name="query"
        required
        placeholder="例如：我已经写作业快一个小时了，现在有10分钟休息。"
        @input="$emit('change', 'query', textValue($event).trim())"
      />
    </label>

    <label>
      学习阶段
      <select
        :value="props.form.target_stage"
        name="target_stage"
        @change="$emit('change', 'target_stage', textValue($event))"
      >
        <option value="primary_upper">小学高年级</option>
        <option value="junior_high">初中</option>
        <option value="senior_high">高中</option>
      </select>
    </label>

    <label>
      当前地点
      <select
        :value="props.form.current_context"
        name="current_context"
        @change="$emit('change', 'current_context', textValue($event))"
      >
        <option value="home">在家</option>
        <option value="school">在学校</option>
        <option value="study_space">学习空间</option>
        <option value="commute">通勤途中</option>
        <option value="bedroom">卧室</option>
        <option value="outdoor">户外</option>
        <option value="unknown">不确定</option>
      </select>
    </label>

    <label>
      当前活动
      <select
        :value="props.form.activity_context"
        name="activity_context"
        @change="$emit('change', 'activity_context', textValue($event))"
      >
        <option value="reading">阅读</option>
        <option value="writing">写作 / 写作业</option>
        <option value="screen">看屏幕</option>
        <option value="other">其他</option>
        <option value="unknown">不确定</option>
      </select>
    </label>

    <label>
      当前可用时间（分钟）
      <input
        :value="props.form.available_minutes ?? ''"
        name="available_minutes"
        type="number"
        min="1"
        required
        @input="$emit('change', 'available_minutes', numberValue($event))"
      />
    </label>

    <fieldset>
      <legend>需要说明的当前情况</legend>
      <label><input :checked="props.form.physical_discomfort" name="physical_discomfort" type="checkbox" @change="$emit('change', 'physical_discomfort', checkedValue($event))" /> 目前有明显身体不适</label>
      <label><input :checked="props.form.vision_abnormal" name="vision_abnormal" type="checkbox" @change="$emit('change', 'vision_abnormal', checkedValue($event))" /> 目前发现明显视力异常</label>
      <label><input :checked="props.form.medical_request" name="medical_request" type="checkbox" @change="$emit('change', 'medical_request', checkedValue($event))" /> 当前正在询问诊断或治疗</label>
      <label><input :checked="props.form.cannot_move" name="cannot_move" type="checkbox" @change="$emit('change', 'cannot_move', checkedValue($event))" /> 当前不方便移动</label>
      <label><input :checked="props.form.unstable_environment" name="unstable_environment" type="checkbox" @change="$emit('change', 'unstable_environment', checkedValue($event))" /> 当前环境晃动或不稳定</label>
      <label><input :checked="props.form.sleep_being_crowded" name="sleep_being_crowded" type="checkbox" @change="$emit('change', 'sleep_being_crowded', checkedValue($event))" /> 学习安排正在明显挤占正常睡眠</label>
    </fieldset>

    <p v-if="loading" aria-live="polite">正在准备一个合适的小行动……</p>
    <div class="actions">
      <button type="submit" :disabled="loading">获取微任务</button>
      <button type="button" :disabled="loading" @click="$emit('reset')">重新填写状态</button>
    </div>
  </form>
</template>
