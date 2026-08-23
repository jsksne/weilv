import { readFile, readdir } from 'node:fs/promises'
import { extname, join } from 'node:path'

const forbiddenPatterns = [
  new RegExp('DASH' + 'SCOPE_' + 'API_' + 'KEY'),
  new RegExp('OPEN' + 'AI_' + 'API_' + 'KEY'),
  new RegExp('\\bapi_' + 'key\\b', 'i'),
  new RegExp('\\bs' + 'k-[A-Za-z0-9_-]+'),
]

async function sourceFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(
    entries.map((entry) => {
      const path = join(directory, entry.name)
      return entry.isDirectory() ? sourceFiles(path) : [path]
    }),
  )
  return files.flat().filter((path) => ['.ts', '.vue'].includes(extname(path)) && !path.endsWith('.test.ts'))
}

it('keeps model secrets outside frontend production source', async () => {
  const files = await sourceFiles(join(process.cwd(), 'src'))

  for (const file of files) {
    const content = await readFile(file, 'utf8')
    for (const pattern of forbiddenPatterns) {
      expect(content, `${file} contains ${pattern}`).not.toMatch(pattern)
    }
  }
})
