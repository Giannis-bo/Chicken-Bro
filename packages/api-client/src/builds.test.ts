import { describe, expect, it } from 'vitest'

import {
  routeContract,
  type BuildsDataStatus,
  type BuildsHomePayload,
  type BuildQuickAction,
  type RaiderIOSummary,
} from '@wow-mini/domain'

import { createBuildsClient, isBuildsHomePayload } from './builds'
import { buildsHomeFallbackSnapshot } from './fallback-snapshots'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

const verifiedAt = '2026-07-14T13:00:00+00:00'
const expiresAt = '2099-07-15T13:00:00+00:00'

const verifiedRaiderio: RaiderIOSummary = {
  sourceName: 'Raider.IO',
  sourceStatus: 'synced',
  sourceStatusLabel: 'Raider.IO synced',
  seasonSlug: 'season-mn-1',
  region: 'cn',
  checkedAt: verifiedAt,
  expiresAt,
  analysisWindow: 'cn season-mn-1',
  sampleCount: 12,
  maxKeyLevel: 18,
  bestScore: 3200,
  sourceUrl: 'https://raider.io/mythic-plus-rankings',
}

function liveHome(overrides: Partial<BuildsHomePayload> = {}): BuildsHomePayload {
  const base = structuredClone(buildsHomeFallbackSnapshot)
  return {
    ...base,
    verifiedAt,
    expiresAt,
    dataStatus: 'verified',
    currentSeason: {
      ...base.currentSeason,
      verifiedAt,
      expiresAt,
      dataStatus: 'verified',
    },
    raiderio: verifiedRaiderio,
    ...overrides,
  }
}

function action(payload: BuildsHomePayload, key: BuildQuickAction['key']): BuildQuickAction {
  const found = payload.quickActions.find((candidate) => candidate.key === key)
  if (!found) throw new Error(`missing ${key} fixture action`)
  return found
}

function omitKeys<T extends object, K extends keyof T>(value: T, ...keys: readonly K[]): Omit<T, K> {
  const copy = { ...value }
  for (const key of keys) Reflect.deleteProperty(copy, key)
  return copy
}

function responseTransport(response: unknown): ApiTransport {
  const respond = async <T>(
    options: Pick<RequestOptions<T>, 'fallback' | 'validate'>,
  ): Promise<ApiResult<T>> => {
    const valid = options.validate?.(response) ?? Boolean(response)
    return valid
      ? { payload: response as T, fromFallback: false, error: '' }
      : { payload: options.fallback(), fromFallback: true, error: 'invalid response payload' }
  }
  return {
    request: (_path, options) => respond(options),
    requestEndpoint: (_endpoint, _path, options) => respond(options),
  }
}

describe('builds home data contract', () => {
  it('accepts a complete response while preserving remote action order and display metadata', async () => {
    const payload = liveHome()
    const talents = action(payload, 'talents')
    const talentsWithoutPhase = omitKeys(talents, 'phaseLabel')
    const quickActions: readonly BuildQuickAction[] = [
      {
        ...action(payload, 'tasks'),
        phaseLabel: '远端追踪',
        actionLabel: '远端任务入口',
        evidenceLabel: '远端任务证据',
      },
      action(payload, 'simc'),
      action(payload, 'gear'),
      talentsWithoutPhase,
    ]
    const remote = {
      ...payload,
      kicker: '远端职业控制台',
      quickActions,
    }

    expect(isBuildsHomePayload(remote)).toBe(true)
    const result = await createBuildsClient(responseTransport(remote)).home()

    expect(result.fromFallback).toBe(false)
    expect(result.payload.kicker).toBe('远端职业控制台')
    expect(result.payload.quickActions.map((item) => item.key)).toEqual(['tasks', 'simc', 'gear', 'talents'])
    expect(result.payload.quickActions[0]).toMatchObject({
      phaseLabel: '远端追踪',
      actionLabel: '远端任务入口',
      evidenceLabel: '远端任务证据',
    })
    expect(result.payload.quickActions[3]?.phaseLabel).toBe('输入')
  })

  it('preserves blocked, partial, and stale payload semantics without promotion', async () => {
    const statuses = ['blocked', 'partial', 'stale'] as const satisfies readonly BuildsDataStatus[]

    for (const status of statuses) {
      const payload = liveHome()
      const remote = {
        ...payload,
        dataStatus: status,
        currentSeason: { ...payload.currentSeason, dataStatus: status },
        raiderio: {
          ...payload.raiderio,
          sourceStatus: status,
          sourceStatusLabel: `Raider.IO ${status}`,
        },
        ...(status === 'blocked'
          ? { blockedReason: '赛季目录未通过官方校验。', classOptions: [] }
          : {}),
      }

      expect(isBuildsHomePayload(remote)).toBe(true)
      const result = await createBuildsClient(responseTransport(remote)).home()

      expect(result.fromFallback).toBe(false)
      expect(result.payload.dataStatus).toBe(status)
      expect(result.payload.currentSeason.dataStatus).toBe(status)
      expect(result.payload.raiderio.sourceStatus).toBe(status)
      if (status === 'blocked') {
        expect(result.payload.blockedReason).toBe('赛季目录未通过官方校验。')
        expect(result.payload.classOptions).toEqual([])
      }
    }
  })

  it('rejects missing status, season, source, and nested identity fields', async () => {
    const payload = liveHome()
    const withoutSourceRefs = omitKeys(payload, 'sourceRefs')
    const withoutRaiderio = omitKeys(payload, 'raiderio')
    const withoutSeasonRevision = {
      ...payload,
      currentSeason: omitKeys(payload.currentSeason, 'revision', 'seasonRevision'),
    }
    const blockedWithoutReason = {
      ...payload,
      dataStatus: 'blocked',
      currentSeason: { ...payload.currentSeason, dataStatus: 'blocked' },
      raiderio: {
        ...payload.raiderio,
        sourceStatus: 'blocked',
        sourceStatusLabel: 'Raider.IO blocked',
        numericValuesUsable: false,
      },
      classOptions: [],
    }
    const firstClass = payload.classOptions[0]
    const firstSpec = firstClass?.specializations[0]
    if (!firstClass || !firstSpec) throw new Error('builds fixture must include a specialization')
    const withoutDisplayIdentity = omitKeys(firstSpec, 'name', 'specName', 'title')
    const withoutNestedIdentity = {
      ...payload,
      classOptions: [
        {
          ...firstClass,
          specializations: [withoutDisplayIdentity, ...firstClass.specializations.slice(1)],
        },
        ...payload.classOptions.slice(1),
      ],
    }

    for (const malformed of [
      withoutSourceRefs,
      withoutRaiderio,
      withoutSeasonRevision,
      blockedWithoutReason,
      withoutNestedIdentity,
    ]) {
      expect(isBuildsHomePayload(malformed)).toBe(false)
      const result = await createBuildsClient(responseTransport(malformed)).home()
      expect(result.fromFallback).toBe(true)
      expect(result.payload.dataStatus).toBe('stale')
      expect(result.payload.currentSeason.dataStatus).toBe('stale')
      expect(result.payload.raiderio.sourceStatus).toBe('blocked')
    }
  })

  it('rejects a nominally successful response missing any required action', async () => {
    const payload = liveHome()
    const remote = {
      ...payload,
      quickActions: payload.quickActions
        .filter((item) => item.key !== 'tasks')
        .map((item) => item.key === 'talents' ? { ...item, title: '不应泄漏的远端标题' } : item),
    }

    expect(isBuildsHomePayload(remote)).toBe(false)
    const result = await createBuildsClient(responseTransport(remote)).home()

    expect(result.fromFallback).toBe(true)
    expect(result.payload.quickActions.map((item) => item.key)).toEqual(['talents', 'gear', 'simc', 'tasks'])
    expect(result.payload.quickActions[0]?.title).not.toBe('不应泄漏的远端标题')
  })

  it('normalizes a missing spec name only from that spec own specName or title', async () => {
    const payload = liveHome()
    const firstClass = payload.classOptions[0]
    const firstSpec = firstClass?.specializations[0]
    const secondSpec = firstClass?.specializations[1]
    if (!firstClass || !firstSpec || !secondSpec) throw new Error('builds fixture needs two specializations')

    const firstWithoutName = omitKeys(firstSpec, 'name')
    const secondWithTitleOnly = omitKeys(secondSpec, 'name', 'specName')
    const remote = {
      ...payload,
      classOptions: [
        {
          ...firstClass,
          specializations: [
            firstWithoutName,
            secondWithTitleOnly,
            ...firstClass.specializations.slice(2),
          ],
        },
        ...payload.classOptions.slice(1),
      ],
    }

    expect(isBuildsHomePayload(remote)).toBe(true)
    const result = await createBuildsClient(responseTransport(remote)).home()
    const normalized = result.payload.classOptions[0]?.specializations

    expect(result.fromFallback).toBe(false)
    expect(normalized?.[0]?.name).toBe(firstSpec.specName)
    expect(normalized?.[1]?.name).toBe(secondSpec.title)
    expect(normalized?.[0]?.className).toBe(firstSpec.className)
    expect(normalized?.[0]?.websimSpecKey).toBe(firstSpec.websimSpecKey)
  })

  it('registers build intel as an outgoing builds home route', () => {
    expect(routeContract('specialization_home/builds_home').outgoing).toContain('build_intel')
  })
})
