import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('formal SimC Mini home', () => {
  it('resolves real source readiness and submits only formal SimC jobs', () => {
    const page = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simc/index.tsx',
    ), 'utf8')
    expect(page).toContain('MiniSessionStore')
    expect(page).toContain('SimcModel')
    expect(page).toContain('.resolveSource(')
    expect(page).toContain('.submitJob(')
    expect(page).toContain('/pages/simc/task-detail')
    expect(page).not.toContain('wowApi.simulator')
    expect(page).not.toContain('exactSimc')
  })
})
