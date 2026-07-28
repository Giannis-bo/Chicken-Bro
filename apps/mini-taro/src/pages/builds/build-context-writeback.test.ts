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
  private readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined {
    return this.values.get(key) as T | undefined
  }

  set<T>(key: string, value: T): void {
    this.values.set(key, value)
  }

  remove(key: string): void {
    this.values.delete(key)
  }
}

function memoryStorage(): StorageAdapter {
  return new MemoryStorage()
}

function read(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('build context specialization writeback', () => {
  it('records the resolved specialization without sharing tool state', () => {
    const context = rememberBuildsHomeSpec(
      { classKey: 'mage', specId: '法师-火焰' },
      emptyBuildsHomeContext(),
      memoryStorage(),
    )

    expect(context.lastSpecByClass).toEqual({ mage: '法师-火焰' })
    expect(JSON.stringify(context)).not.toMatch(/hero|template|draft|submission|gear|buildContext|task/u)
  })

  it('uses the shared specialization writeback helper in every tool page', () => {
    expect(read('apps/mini-taro/src/pages/builds/talent-simulator.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
    expect(read('apps/mini-taro/src/pages/builds/detail.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
    expect(read('apps/mini-taro/src/pages/simulator/simc.tsx')).toContain('rememberBuildsHomeSpec(data.selection)')
  })

  it('persists a gear specialization choice before starting its async route reload', () => {
    const source = read('apps/mini-taro/src/pages/builds/detail.tsx')
    const handler = source.match(
      /const selectSpecialization = \(item: GearSpecializationItem\) => \{([\s\S]*?)\n[ ]{2}\}/u,
    )?.[1] ?? ''

    expect(handler).toMatch(
      /rememberBuildsHomeSpec\(\{ classKey: data\.selection\.classKey, specId: item\.id \}\)[\s\S]*setSelectedSpecId\(item\.id\)/u,
    )
    expect(source).toContain('onSelect={selectSpecialization}')
  })

  it.each([
    'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    'apps/mini-taro/src/pages/builds/detail.tsx',
    'apps/mini-taro/src/pages/simulator/simc.tsx',
  ])('guards resolved class/spec identities before writeback in %s', (path) => {
    expect(read(path)).toMatch(/const resolvedClassKey = data\?\.selection\.classKey\s+const resolvedSpecId = data\?\.selection\.specId\s+useEffect\(\(\) => \{\s+if \(!data\?\.selection \|\| !resolvedClassKey \|\| !resolvedSpecId\) return\s+rememberBuildsHomeSpec\(data\.selection\)\s+\}, \[resolvedClassKey, resolvedSpecId\]\)/u)
  })
})
