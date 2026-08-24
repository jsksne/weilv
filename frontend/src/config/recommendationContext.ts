import type { ActivityContext, CurrentContext } from '@/api/types'

/**
 * Sprint 9：Production Today/Assistant 推荐请求的基础上下文 seam。
 *
 * 冻结 Today UI 没有查询输入框，而现有 Recommendation API 要求 query。
 * 这里提供一个显式、可替换的默认 query（可用 VITE_TODAY_QUERY 覆盖），
 * 避免前端伪造"用户当前困扰"。current_context 使用后端安全的 'unknown'。
 * target_stage 由已加载的真实 Profile 派生（见 ApiUiDataSource），不在此配置。
 */
export const TODAY_QUERY_ENV_KEY = 'VITE_TODAY_QUERY'

export const DEFAULT_TODAY_QUERY = '请为我推荐一个适合现在完成的微任务。'

export interface RecommendationContext {
  query: string
  current_context: CurrentContext
  activity_context: ActivityContext
}

export function getConfiguredRecommendationContext(): RecommendationContext {
  const query = (import.meta.env.VITE_TODAY_QUERY as string | undefined)?.trim()
  return {
    query: query || DEFAULT_TODAY_QUERY,
    current_context: 'unknown',
    activity_context: 'unknown',
  }
}
