import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function read(fileName: string): string {
  return readFileSync(resolve(process.cwd(), 'packages/design-system/src/components', fileName), 'utf8')
}

describe('builds home recent SimC task preview component', () => {
  it('publishes stable task preview roles without readiness or numeric-result copy', () => {
    const source = read('BuildRecentSimcTasks.tsx')

    expect(source).toContain('data-owner="build-recent-simc-tasks"')
    expect(source).toContain('data-role="build-recent-simc-row"')
    expect(source).toContain('data-role="build-recent-simc-retry"')
    expect(source).not.toMatch(/DPS|准备状态|模板状态/u)
  })

  it('exports the component and its isolated item contract', () => {
    const source = readFileSync(resolve(process.cwd(), 'packages/design-system/src/index.ts'), 'utf8')

    expect(source).toContain("export { BuildRecentSimcTasks } from './components/BuildRecentSimcTasks'")
    expect(source).toContain("export type { BuildRecentSimcTaskItem, BuildRecentSimcTasksProps } from './components/BuildRecentSimcTasks'")
  })
})
