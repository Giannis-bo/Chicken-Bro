import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/components', () => ({
  Button: 'button',
  Image: 'image',
  Text: 'text',
  View: 'view',
}))

import * as recentSimcTasks from './BuildRecentSimcTasks'

function read(fileName: string): string {
  return readFileSync(resolve(process.cwd(), 'packages/design-system/src/components', fileName), 'utf8')
}

describe('builds home recent SimC task preview component', () => {
  it('keeps three full task slots for empty and partial recent-task states', () => {
    const resolveRows = (recentSimcTasks as {
      resolveRecentSimcTaskRows?: (
        items: readonly {
          id: string
          title: string
          detail: string
          state: 'queued' | 'running' | 'failed' | 'completed' | 'unknown'
          stateLabel: string
          timeLabel: string
          navigable: boolean
        }[],
        state: 'loading' | 'ready' | 'empty' | 'error',
      ) => readonly { id: string; title: string; placeholder?: boolean }[]
    }).resolveRecentSimcTaskRows

    expect(resolveRows).toBeTypeOf('function')

    const emptyRows = resolveRows?.([], 'empty')
    expect(emptyRows).toHaveLength(3)
    expect(emptyRows?.map((item) => item.title)).toEqual([
      '暂无 SimC 任务',
      '等待新的模拟任务',
      '等待新的模拟任务',
    ])
    expect(emptyRows?.every((item) => item.placeholder === true)).toBe(true)

    const partialRows = resolveRows?.([
      {
        id: 'latest-task',
        title: '法师 · 冰霜',
        detail: '大秘境基准',
        state: 'completed',
        stateLabel: '已完成',
        timeLabel: '刚刚',
        navigable: true,
      },
    ], 'ready')
    expect(partialRows).toHaveLength(3)
    expect(partialRows?.map((item) => item.id)).toEqual([
      'latest-task',
      'empty-slot-2',
      'empty-slot-3',
    ])
  })

  it('publishes stable task preview roles without readiness or numeric-result copy', () => {
    const source = read('BuildRecentSimcTasks.tsx')

    expect(source).toContain('data-owner="build-recent-simc-tasks"')
    expect(source).toContain('data-role="build-recent-simc-row"')
    expect(source).toContain('data-role="build-recent-simc-retry"')
    expect(source).toContain("data-placeholder={item.placeholder === true ? 'true' : 'false'}")
    expect(source).not.toMatch(/DPS|准备状态|模板状态/u)
  })

  it('uses all available preview height for three full-width task rows', () => {
    const styles = read('BuildsHomeCommandDeck.module.scss')

    expect(styles).toMatch(/\.recentSimcRows \{[\s\S]*?grid-template-rows:\s*repeat\(3, minmax\(0, 1fr\)\);/u)
    expect(styles).toMatch(/button\.recentSimcRow \{[\s\S]*?display:\s*grid;[\s\S]*?width:\s*100%;[\s\S]*?height:\s*100%;/u)
  })

  it('exports the component and its isolated item contract', () => {
    const source = readFileSync(resolve(process.cwd(), 'packages/design-system/src/index.ts'), 'utf8')

    expect(source).toContain("export { BuildRecentSimcTasks } from './components/BuildRecentSimcTasks'")
    expect(source).toContain("export type { BuildRecentSimcTaskItem, BuildRecentSimcTasksProps } from './components/BuildRecentSimcTasks'")
  })
})
