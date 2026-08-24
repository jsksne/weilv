import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const srcDir = dirname(fileURLToPath(import.meta.url))
const contractsDir = join(srcDir, 'contracts')
const canonicalContractFiles = [
  'common.ts',
  'shell.ts',
  'today.ts',
  'assistant.ts',
  'profile.ts',
  'weekly.ts',
  'onboarding.ts',
  'uiDataSource.ts',
  'index.ts',
]

describe('Sprint 2R contract boundary', () => {
  it('provides every canonical contract module', () => {
    const missing = canonicalContractFiles.filter(file => !existsSync(join(contractsDir, file)))

    expect(missing).toEqual([])
  })

  it('keeps canonical contracts independent from backend DTO types', () => {
    const files = canonicalContractFiles.filter(file => existsSync(join(contractsDir, file)))
    const imports = files.flatMap(file => {
      const source = readFileSync(join(contractsDir, file), 'utf8')
      return source.match(/(?:from|import)\s+['"][^'"]*api\/types[^'"]*['"]/g) ?? []
    })

    expect(imports).toEqual([])
  })

  it('provides a shell fixture without business payloads', () => {
    const fixturePath = join(srcDir, 'data', 'fixtures', 'shell.fixture.ts')
    expect(existsSync(fixturePath)).toBe(true)

    const source = existsSync(fixturePath) ? readFileSync(fixturePath, 'utf8') : ''
    expect(source).not.toMatch(/recommendation|health|memory|agentic|trace/i)
  })

  it('activates the Sprint 6 visual assets while keeping Weekly CSS out of the entrypoint', () => {
    const entry = readFileSync(join(srcDir, 'styles', 'index.css'), 'utf8')

    expect(entry).toContain("@import '../style.css'")
    for (const asset of ['tokens', 'typography', 'glass', 'animations', 'aurora', 'effects', 'accessibility']) {
      expect(entry).toContain(`@import './${asset}.css'`)
    }
    /* Sprint 4/5/6：Today、Assistant 与 Profile/Onboarding 页面正式激活 */
    expect(entry).toContain("@import './today.css'")
    expect(entry).toContain("@import './assistant.css'")
    expect(entry).toContain("@import './profile.css'")
    expect(entry).toContain("@import './onboarding.css'")
    expect(entry).not.toContain("@import './weekly.css'")
  })
})
