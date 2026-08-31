import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { mount } from '@vue/test-utils'

import DustField from './components/effects/DustField.vue'
import PetalField from './components/effects/PetalField.vue'

describe('mobile visual budget', () => {
  it('keeps desktop density and reduces only the compact viewport density', () => {
    const desktopPetals = mount(PetalField)
    const desktopDust = mount(DustField)
    expect(desktopPetals.findAll('.petal')).toHaveLength(26)
    expect(desktopDust.findAll('.dust')).toHaveLength(54)
    desktopPetals.unmount()
    desktopDust.unmount()

    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(375)
    const mobilePetals = mount(PetalField)
    const mobileDust = mount(DustField)
    expect(mobilePetals.findAll('.petal')).toHaveLength(18)
    expect(mobileDust.findAll('.dust')).toHaveLength(32)
    mobilePetals.unmount()
    mobileDust.unmount()
  })

  it('caps compact DOM paints without slowing the falling motion', () => {
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(375)
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => {
      frames.push(callback)
      return frames.length
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})
    vi.spyOn(performance, 'now').mockReturnValue(0)
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    const frames: FrameRequestCallback[] = []
    const wrapper = mount(PetalField)
    const petal = wrapper.get<HTMLElement>('.petal').element
    const y = () => Number(/translate\([^,]+,\s*([-\d.]+)px/.exec(petal.style.transform)?.[1])

    const initialY = y()
    frames.shift()!(16)
    const firstPaintY = y()
    frames.shift()!(32)
    expect(y()).toBe(firstPaintY)
    frames.shift()!(50)

    expect(y() - firstPaintY).toBeGreaterThan((firstPaintY - initialY) * 1.5)
    wrapper.unmount()
  })

  it('uses compact navigation and mood layout rules without removing animation layers', () => {
    const styles = readFileSync(join(process.cwd(), 'src/styles/navigation.css'), 'utf8')
    const todayStyles = readFileSync(join(process.cwd(), 'src/styles/today.css'), 'utf8')
    const auroraStyles = readFileSync(join(process.cwd(), 'src/styles/aurora.css'), 'utf8')

    expect(styles).toContain('@media (max-width: 560px)')
    expect(styles).toContain('white-space: nowrap')
    expect(styles).toContain('min-height: 40px')
    expect(styles).toContain('backdrop-filter: blur(12px)')
    expect(styles).toContain('html { overflow-x: clip; }')
    expect(todayStyles).toContain('grid-template-columns: repeat(4, minmax(0, 1fr))')
    expect(auroraStyles).toContain('@media (max-width: 768px)')
    expect(auroraStyles).toContain('.blob { filter: blur(72px); }')
  })

  it('keeps the mobile send action on one readable line', () => {
    const styles = readFileSync(join(process.cwd(), 'src/styles/assistant.css'), 'utf8')

    expect(styles).toMatch(/\.btn-send\s*\{[^}]*white-space:\s*nowrap/)
    expect(styles).toContain('.ask-input { flex-wrap: nowrap; gap: 8px; }')
  })
})
