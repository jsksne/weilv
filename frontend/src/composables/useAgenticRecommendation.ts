import { ref } from 'vue'

import type {
  AssistantPipeline,
  AssistantReply,
  ConversationTurn,
  UiDataSource,
} from '@/contracts'
import { applyAgentTraceEvent, createLiveTracePipeline } from '@/data/adapters'

/**
 * F1：连续对话。会话按顺序保留所有问答；每次请求携带最近若干完整轮次，
 * 真实进入后端理解环节（不写 Memory、不改变安全分流）。单个会话同一
 * 时刻只运行一个回答请求；重试原位覆盖，不重复追加用户消息。
 */

export interface ConversationMessage {
  id: number
  question: string
  /** 易启动开关在本轮提问时的取值（重试沿用）。 */
  easyStart?: boolean
  reply: AssistantReply | null
  /** 流式期间的实时 pipeline（仅由真实 trace 事件推进）。 */
  pipeline: AssistantPipeline | null
  status: 'pending' | 'complete' | 'error' | 'stopped'
  errorMessage: string | null
  /** 流式通道失败后由非流式端点完成同一流程时置位（如实提示）。 */
  streamFallbackUsed: boolean
}

/** 受模型上下文预算约束：最多携带最近 6 轮（12 条 turn）。 */
const MAX_HISTORY_TURNS = 6

function replyToHistoryText(reply: AssistantReply): string {
  const answer = reply.answer.map(segment => segment.text).join('')
  const suggestion = reply.suggestedTask ? `（建议的小事：${reply.suggestedTask.title}）` : ''
  const text = `${answer}${suggestion}`.trim()
  return text || '（本轮回答未生成文本内容）'
}

export function useAgenticRecommendation(source: UiDataSource | null) {
  const messages = ref<ConversationMessage[]>([])
  const busy = ref(false)
  const renderVersion = ref(0)
  let nextId = 1

  /** 最近完整问答转为请求历史；出错/被停止的轮次不进入上下文。 */
  function historyTurns(excludeId?: number): ConversationTurn[] {
    const turns: ConversationTurn[] = []
    for (const message of messages.value) {
      if (message.id === excludeId) continue
      if (message.status !== 'complete' || !message.reply) continue
      turns.push({ role: 'user', content: message.question })
      turns.push({ role: 'assistant', content: replyToHistoryText(message.reply) })
    }
    return turns.slice(-MAX_HISTORY_TURNS * 2)
  }

  function patchMessage(id: number, patch: Partial<ConversationMessage>): void {
    messages.value = messages.value.map(message =>
      message.id === id ? { ...message, ...patch } : message,
    )
  }

  async function ask(message: ConversationMessage, options: { easyStart?: boolean } = {}): Promise<boolean> {
    if (!source) return false
    const history = historyTurns(message.id)
    patchMessage(message.id, {
      status: 'pending',
      reply: null,
      pipeline: null,
      errorMessage: null,
      streamFallbackUsed: false,
    })
    busy.value = true
    renderVersion.value += 1
    const { question, id } = message
    try {
      if (source.askAssistantStreaming) {
        try {
          const reply = await source.askAssistantStreaming(
            question,
            event => {
              // 只有真实 backend 事件才会推进 pipeline；没有事件就不会自行前进。
              const current = messages.value.find(item => item.id === id)
              const base = current?.pipeline ?? createLiveTracePipeline()
              patchMessage(id, { pipeline: applyAgentTraceEvent(base, event) })
              renderVersion.value += 1
            },
            history,
            options.easyStart,
          )
          patchMessage(id, { reply, pipeline: null, status: 'complete' })
          return true
        } catch (streamCause) {
          /* 网关可能不支持流式响应（如 PocketBay 返回 403/204）：
             回退到非流式端点完成同一条 Agentic 管线，而不是让用户卡在报错。 */
          if (typeof source.askAssistant !== 'function') throw streamCause
          const reply = await source.askAssistant(question, history, options.easyStart)
          patchMessage(id, { reply, pipeline: null, status: 'complete', streamFallbackUsed: true })
          return true
        }
      }
      const reply = await source.askAssistant(question, history, options.easyStart)
      patchMessage(id, { reply, pipeline: null, status: 'complete' })
      return true
    } catch (cause) {
      patchMessage(id, {
        status: 'error',
        pipeline: null,
        errorMessage: cause instanceof Error ? cause.message : 'Agentic 推荐失败。',
      })
      return false
    } finally {
      busy.value = false
      renderVersion.value += 1
    }
  }

  async function submit(
    rawQuestion: string,
    options: { easyStart?: boolean } = {},
  ): Promise<boolean> {
    const question = rawQuestion.trim()
    if (!question || busy.value || !source) return false
    const message: ConversationMessage = {
      id: nextId++,
      question,
      easyStart: options.easyStart,
      reply: null,
      pipeline: null,
      status: 'pending',
      errorMessage: null,
      streamFallbackUsed: false,
    }
    messages.value = [...messages.value, message]
    return ask(message, options)
  }

  /** 原位重试最后一轮；不重复追加用户消息。 */
  async function retry(messageId: number): Promise<boolean> {
    if (busy.value || messages.value.length === 0) return false
    const last = messages.value[messages.value.length - 1]
    if (!last || last.id !== messageId) return false
    if (last.status !== 'error' && last.status !== 'stopped') return false
    return ask(last, { easyStart: last.easyStart })
  }

  /** 清空会话上下文；不删除今日任务、画像或已授权记忆。 */
  function startNewConversation(): boolean {
    if (busy.value) return false
    messages.value = []
    renderVersion.value += 1
    return true
  }

  return { messages, busy, renderVersion, submit, retry, startNewConversation }
}
