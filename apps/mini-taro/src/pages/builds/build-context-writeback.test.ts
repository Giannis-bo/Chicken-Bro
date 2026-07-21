import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import type { StorageAdapter } from '@wow-mini/api-client'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@wow-mini/api-client', () => ({ taroStorage: undefined }))
vi.mock('@wow-mini/domain', () => ({
  storageKey: (id: string) => {
    if (id !== 'builds.homeContext') throw new Error(`Unexpected storage id: ${id}`)
    return 'wow_builds_home_context_v1'
  },
}))

import { emptyBuildsHomeContext } from '../_shared/build-context'
import { rememberBuildsHomeSpec } from '../_shared/build-context-storage'

class MemoryStorage implements StorageAdapter {
  get<T>(_key: string): T | undefined {
    return undefined
  }

  set<T>(_key: string, _value: T): void {}

  remove(_key: string): void {}
}

function memoryStorage(): StorageAdapter {
  return new MemoryStorage()
}

function read(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('build context specialization writeback', () => {
  it('records the resolved specialization without sharing hero, template, draft, or submission state', () => {
    const context = rememberBuildsHomeSpec(
      { classKey: 'mage', specId: '法师-火焰' },
      emptyBuildsHomeContext(),
      memoryStorage(),
    )

    expect(context.lastSpecByClass).toEqual({ mage: '法师-火焰' })
    expect(JSON.stringify(context)).not.toMatch(/hero|template|draft|submission/u)
  })

  it('uses the shared specialization writeback helper in every tool page', () => {
    expect(read('apps/mini-taro/src/pages/builds/talent-simulator.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
    expect(read('apps/mini-taro/src/pages/builds/detail.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
    expect(read('apps/mini-taro/src/pages/simulator/simc.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
  })
})
