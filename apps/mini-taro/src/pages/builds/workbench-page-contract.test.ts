import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('current specialization workbench page contract', () => {
  it('connects the shared header menu owner to profile template management', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/workbench.tsx',
    ), 'utf8')

    expect(source).toContain('WorkbenchMenuAction')
    expect(source).toContain('rightAction={<WorkbenchMenuAction')
    expect(source).toContain("Taro.switchTab({ url: '/pages/profile/profile' })")
  })
})
