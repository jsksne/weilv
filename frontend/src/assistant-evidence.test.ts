import { mount } from '@vue/test-utils'

import EvidenceList from './components/assistant/EvidenceList.vue'

describe('Assistant evidence disclosure', () => {
  it('collapses citations and removes duplicate source identities', () => {
    const wrapper = mount(EvidenceList, {
      props: {
        sources: [
          { label: '同一审核条目', url: '/knowledge/sleep#1' },
          { label: '重复的同一审核条目', url: '/knowledge/sleep#1' },
          { label: '没有链接的条目' },
          { label: '没有链接的条目' },
        ],
      },
    })

    const details = wrapper.get('[data-testid="evidence-list"]')
    expect(details.element.tagName).toBe('DETAILS')
    expect(details.attributes('open')).toBeUndefined()
    expect(details.get('summary').text()).toContain('依据来源 · 2 条')
    expect(details.findAll('a')).toHaveLength(2)
    expect(details.findAll('a')[0].attributes('href')).toBe('/knowledge/sleep#1')
  })
})
