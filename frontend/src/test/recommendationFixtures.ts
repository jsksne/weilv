import type { RecommendationResponse } from '@/api/types'

export const allowedRecommendation: RecommendationResponse = {
  status: 'allowed',
  selected_task: {
    task_id: 'MT-SED-001',
    title: '写作业久坐后的起身活动',
    instruction: '起身活动约10分钟再继续。',
    evidence_chunk_ids: ['KC-SRC-007-003'],
    covered_domains: ['sedentary', 'light_recovery'],
    estimated_minutes: 10,
  },
  explanation: '这个任务适合当前短暂休息的情境。',
  sources: [
    {
      chunk_id: 'KC-SRC-007-003',
      document_id: 'SRC-007',
      source_locator: 'source.md:L20-L20',
      source_url: 'https://example.test/source',
    },
  ],
  context_sources: [
    {
      chunk_id: 'KC-CONTEXT-001',
      document_id: 'SRC-CONTEXT',
      source_locator: 'context.md:L10-L12',
      source_url: 'https://example.test/context',
    },
  ],
  matched_rule_ids: [],
  reason_codes: [],
  explanation_guard: {
    passed: true,
    fallback_used: false,
    reason_codes: [],
  },
  personalization: null,
  recommendation_id: 'rec-001',
  feedback_available: true,
}

export function nonAllowedRecommendation(
  status: 'blocked' | 'help_seeking' | 'no_safe_task',
): RecommendationResponse {
  return {
    status,
    selected_task: null,
    explanation: null,
    sources: [],
    context_sources: null,
    matched_rule_ids: ['SR-001'],
    reason_codes: [`${status}_reason`],
    explanation_guard: null,
    personalization: null,
    recommendation_id: null,
    feedback_available: false,
  }
}
