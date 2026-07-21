import { storageKey, type BuildsHomePayload } from '@wow-mini/domain'
import type { StorageAdapter } from '@wow-mini/api-client'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@wow-mini/api-client', () => ({ taroStorage: undefined }))
vi.mock('@wow-mini/domain', () => ({
  storageKey: (id: string) => {
    if (id !== 'builds.homeContext') throw new Error(`Unexpected storage id: ${id}`)
    return 'wow_builds_home_context_v1'
  },
}))

import {
  emptyBuildsHomeContext,
  resolveBuildsHomeLaunch,
} from './build-context'
import {
  readBuildsHomeContext,
  rememberBuildsHomeSpec,
  selectBuildsHomeClass,
} from './build-context-storage'

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

function payload(overrides: Partial<BuildsHomePayload> = {}): BuildsHomePayload {
  return {
    navTitle: '职业专精',
    kicker: '职业控制台',
    title: '职业专精',
    desc: '目录',
    dataStatus: 'verified',
    currentSeason: { dataStatus: 'verified' },
    raiderio: { sourceStatus: 'blocked', sampleCount: 0 },
    quickActions: [],
    featuredSpecializations: [],
    trustedSources: [],
    sourceRefs: [],
    classOptions: [
      {
        name: '战士',
        websimClassKey: 'warrior',
        specializations: [{ name: '武器', id: '战士-武器', sourceName: 'test', sourceUrl: 'https://example.test' }],
      },
      {
        name: '法师',
        websimClassKey: 'mage',
        specializations: [
          { name: '冰霜', id: '法师-冰霜', sourceName: 'test', sourceUrl: 'https://example.test' },
          { name: '奥术', id: '法师-奥术', sourceName: 'test', sourceUrl: 'https://example.test' },
        ],
      },
    ],
    ...overrides,
  }
}

function emptyPayload(): BuildsHomePayload {
  return payload({
    classOptions: [
      { name: '战士', websimClassKey: 'warrior', specializations: [] },
      { name: '法师', websimClassKey: 'mage', specializations: [] },
    ],
  })
}

describe('builds home launch context', () => {
  it('keeps a valid remembered specialization for the selected class', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'mage',
      lastSpecByClass: { mage: '法师-奥术' },
    })

    expect(launch?.classKey).toBe('mage')
    expect(launch?.selection.specId).toBe('法师-奥术')
  })

  it('falls back to the first valid specialization of the selected class', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'mage',
      lastSpecByClass: { mage: '失效-专精' },
    })

    expect(launch?.selection.specId).toBe('法师-冰霜')
  })

  it('falls back to the class containing the default specialization when the selected class is invalid', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'missing',
      lastSpecByClass: {},
    })

    expect(launch).toMatchObject({ classKey: 'mage', selection: { specId: '法师-冰霜' } })
  })

  it('does not create a launch context when every class has no specialization', () => {
    expect(resolveBuildsHomeLaunch(emptyPayload(), emptyBuildsHomeContext())).toBeNull()
  })

  it.each(['{not json', JSON.stringify({ selectedClassKey: 'mage', lastSpecByClass: { mage: '' } })])(
    'fails safe for malformed persisted context: %s',
    (stored) => {
      const storage = new MemoryStorage()
      storage.set(storageKey('builds.homeContext'), stored)

      expect(readBuildsHomeContext(storage)).toEqual(emptyBuildsHomeContext())
    },
  )

  it('does not let another class remembered specialization affect the selected class', () => {
    const launch = resolveBuildsHomeLaunch(payload(), {
      selectedClassKey: 'mage',
      lastSpecByClass: { warrior: '战士-武器' },
    })

    expect(launch).toMatchObject({ classKey: 'mage', selection: { specId: '法师-冰霜' } })
  })

  it('persists only the selected class and per-class remembered specialization', () => {
    const storage = new MemoryStorage()
    const selected = selectBuildsHomeClass('mage', storage)
    const remembered = rememberBuildsHomeSpec({ classKey: 'mage', specId: '法师-奥术' }, selected, storage)

    expect(remembered).toEqual({ selectedClassKey: 'mage', lastSpecByClass: { mage: '法师-奥术' } })
    expect(readBuildsHomeContext(storage)).toEqual(remembered)
  })
})
