import { describe, expect, it } from 'vitest'

import type { WebsimTalentsPayload } from '@wow-mini/domain'

import { createWebsimClient, normalizeTalentNode } from './websim'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

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

function rawTalents(): WebsimTalentsPayload {
  return {
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'frostfire',
    nodes: [
      {
        id: 'root',
        name: '根节点',
        treeType: 'class',
        row: 1,
        col: 4,
        selectedRank: 1,
        maxRank: 2,
        pointRequirement: 0,
        parentIds: [],
        shape: 'circle',
        granted: true,
      },
      {
        id: 'child',
        name: '子节点',
        treeType: 'class',
        row: 2,
        col: 3,
        selectedRank: 0,
        maxRank: 1,
        pointRequirement: 1,
        parentIds: ['root'],
        parentMode: 'all',
      },
    ] as unknown as WebsimTalentsPayload['nodes'],
    treeSections: [{ key: 'class', title: '法师', pointCap: 34 }],
    presets: [],
    communityTemplates: [],
    talentStatus: 'simc',
    errors: [],
  }
}

describe('websim talent normalization', () => {
  it('maps backend rule fields into the canonical typed node contract', () => {
    const normalized = normalizeTalentNode(rawTalents().nodes[1])

    expect(normalized).toMatchObject({
      id: 'child',
      treeKey: 'class',
      column: 3,
      ranks: 0,
      requiredPoints: 1,
      prerequisiteIds: ['root'],
      parentMode: 'all',
    })
  })

  it('normalizes live payloads once at the API-client boundary', async () => {
    const result = await createWebsimClient(responseTransport(rawTalents())).talents({
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
    })

    expect(result.fromFallback).toBe(false)
    expect(result.payload.nodes).toHaveLength(2)
    expect(result.payload.nodes[0]).toMatchObject({
      column: 4,
      ranks: 1,
      requiredPoints: 0,
      treeKey: 'class',
      granted: true,
    })
    expect(result.payload.nodes[1]?.prerequisiteIds).toEqual(['root'])
  })

  it('never treats the backend rank field as selected rank', () => {
    const normalized = normalizeTalentNode({
      id: 'unselected',
      name: '未选择',
      treeType: 'spec',
      rank: 3,
      maxRank: 3,
      selectedRank: 0,
    })

    expect(normalized?.ranks).toBe(0)
    expect(normalized?.maxRank).toBe(3)
  })
})
