import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const srcDir = dirname(fileURLToPath(import.meta.url))
const forbiddenThemeCopy = ['春日极光', '春樱', '极光智能感', '春樱基底', '极光主题', '春日微光']

function collectRuntimeSource(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectRuntimeSource(path)
    if (!entry.isFile() || entry.name.endsWith('.test.ts')) return []
    if (!path.endsWith('.vue') && !path.endsWith('.ts')) return []
    return [path]
  })
}

describe('Sprint 10.2 runtime theme-copy scan', () => {
  it('does not expose visual-theme marketing copy in frontend runtime source', () => {
    const hits = collectRuntimeSource(srcDir).flatMap(path => {
      const source = readFileSync(path, 'utf8')
      return forbiddenThemeCopy
        .filter(term => source.includes(term))
        .map(term => `${relative(srcDir, path)}: ${term}`)
    })

    expect(hits).toEqual([])
  })
})
