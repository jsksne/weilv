import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { adaptAgenticRecommendation } from './data/adapters'
import { allowedRecommendation, nonAllowedRecommendation } from './test/recommendationFixtures'
import type { AgenticRecommendationResponse } from './api/types'

const srcDir = dirname(fileURLToPath(import.meta.url))

function agentic(dto: typeof allowedRecommendation): AgenticRecommendationResponse {
  return { ...dto, agentic: true, diagnostics: { knowledge_chunk_ids_by_factor: { F1: ['chunk-id-only'] } } }
}

describe('Assistant DTO adapter boundary', () => {
  it('maps final DTO fields and exposes unavailable production stages', () => {
    const reply = adaptAgenticRecommendation(agentic(allowedRecommendation))

    expect(reply.answer).toEqual([{ text: allowedRecommendation.explanation }])
    expect(reply.suggestedTask?.title).toBe(allowedRecommendation.selected_task?.title)
    expect(reply.sources.map(source => source.label)).toEqual([
      'source.md:L20-L20',
      'context.md:L10-L12',
    ])
    expect(reply.pipeline.analysis.status).toBe('unavailable')
    expect(reply.pipeline.retrieval.status).toBe('unavailable')
    expect(reply.pipeline.retrieval.chunks).toEqual([])
    expect(reply.pipeline.answer.status).toBe('done')
    expect(reply.timing).toBeNull()
    expect(reply.traceIsReal).toBe(false)
  })

  it('uses structured Safety status and never text-matches the answer', () => {
    const safetyReply = adaptAgenticRecommendation(agentic(nonAllowedRecommendation('help_seeking')))
    const allowedWithRiskWord = adaptAgenticRecommendation(
      agentic({ ...allowedRecommendation, explanation: '我脖子疼，但这里只是后端回答文本。' }),
    )

    expect(safetyReply.safety?.status).toBe('help_seeking')
    expect(allowedWithRiskWord.safety).toBeNull()
  })

  it('does not call the network and keeps production chunk content unavailable', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const reply = adaptAgenticRecommendation(agentic(allowedRecommendation))

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(reply.pipeline.analysis.items).toEqual([])
    expect(reply.pipeline.retrieval.chunks).toEqual([])
  })
})

describe('Assistant rendering safety boundary', () => {
  it('uses controlled Vue text rendering without v-html or innerHTML', () => {
    const paths = [
      join(srcDir, 'views', 'AssistantView.vue'),
      ...['components/assistant', 'composables'].flatMap(directory => {
        const path = join(srcDir, directory)
        return directory === 'components/assistant'
          ? ['AssistantHero.vue', 'QuickPromptList.vue', 'ConversationLog.vue', 'UserMessage.vue', 'AgentPipeline.vue', 'PipelineRail.vue', 'PipelineStage.vue', 'ProblemAnalysisStage.vue', 'KnowledgeRetrievalStage.vue', 'KnowledgeChunk.vue', 'AnswerCard.vue', 'SuggestedMiniTask.vue', 'SafetyNotice.vue', 'EvidenceList.vue'].map(file => join(path, file))
          : [join(path, 'useAssistantFlow.ts')]
      }),
    ]

    for (const path of paths) {
      const source = readFileSync(path, 'utf8')
      expect(source).not.toMatch(/v-html|innerHTML/)
    }
  })
})
