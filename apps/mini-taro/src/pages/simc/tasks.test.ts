import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('formal SimC task history', () => {
  it('loads server-owned formal job history and opens a formal detail route', () => {
    const page = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simc/tasks.tsx',
    ), 'utf8')
    expect(page).toContain('.loadJobs(')
    expect(page).toContain('/pages/simc/task-detail')
    expect(page).not.toContain('wowApi.simulator')
    expect(page).not.toContain('guest')
  })
})
