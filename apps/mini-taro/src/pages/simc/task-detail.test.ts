import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('formal SimC task detail', () => {
  it('polls bounded formal status and renders semantic result provenance', () => {
    const page = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simc/task-detail.tsx',
    ), 'utf8')
    expect(page).toContain('.pollJob(')
    expect(page).toContain('metricValue')
    expect(page).toContain('runtimeRevision')
    expect(page).toContain('profileSha256')
    expect(page).not.toContain('stdout')
    expect(page).not.toContain('returncode')
  })
})
