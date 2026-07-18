import { describe, expect, it } from 'vitest'

import type {
  TalentApiExportPayload,
  TalentApiImportPayload,
  TalentValidationPayload,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

import {
  createWebsimClient,
  isTalentExportPayload,
  isTalentImportPayload,
  isTalentValidationPayload,
  normalizeTalentNode,
} from './websim'
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
  it('preserves the legacy choice and granted-rank semantics needed by the talent tree', () => {
    const normalized = normalizeTalentNode({
      id: 'choice-a',
      name: '选项甲',
      treeType: 'spec',
      row: 3,
      col: 4,
      selectedRank: 0,
      grantedRank: 1,
      nodeType: 2,
      choiceGroup: 'spec-row-3',
      parentIds: ['root'],
      pointRequirement: 8,
    })

    expect(normalized).toMatchObject({
      column: 4,
      ranks: 0,
      grantedRank: 1,
      nodeType: 2,
      choiceGroup: 'spec-row-3',
      prerequisiteIds: ['root'],
      requiredPoints: 8,
    })
  })

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

describe('authoritative talent edit endpoints', () => {
  const validation: TalentValidationPayload = {
    classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
    status: 'encoded', source: 'simc', schemaRevision: 'websim-talent-rules-v1',
    errors: [], warnings: [], lines: ['class_talents=1:1'],
    selectedCounts: { class: 1, spec: 0, hero: 0 },
    talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
    talentSchemaRevision: 'websim-talent-rules-v1', blockers: [],
  }
  const exported: TalentApiExportPayload = {
    classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
    talentState: validation.talentState,
    websimExportCode: 'websim:mage:frost:frostfire:root:1',
    validation,
    talentSchemaRevision: 'websim-talent-rules-v1',
  }
  const imported: TalentApiImportPayload = {
    classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
    talentState: validation.talentState,
    validation,
    talentSchemaRevision: 'websim-talent-rules-v1',
  }

  it('accepts complete backend payloads and rejects malformed nested contract data', () => {
    expect(isTalentValidationPayload(validation)).toBe(true)
    expect(isTalentExportPayload(exported)).toBe(true)
    expect(isTalentImportPayload(imported)).toBe(true)

    const invalidValidations: unknown[] = [
      { ...validation, classKey: 7 },
      { ...validation, status: '' },
      { ...validation, source: '' },
      { ...validation, schemaRevision: '' },
      { ...validation, blockers: ['blocked', 7] },
      { ...validation, errors: 'bad' },
      { ...validation, selectedCounts: { class: 1, spec: 0 } },
      { ...validation, selectedCounts: { class: '1', spec: 0, hero: 0 } },
      { ...validation, talentState: { selectedNodes: [{ id: '', rank: 1 }] } },
      { ...validation, talentState: { selectedNodes: [{ id: 'root', rank: Number.NaN }] } },
      { ...validation, talentState: { selectedNodes: ['root'] } },
    ]
    expect(invalidValidations.every((value) => !isTalentValidationPayload(value))).toBe(true)

    expect(isTalentExportPayload({ ...exported, websimExportCode: 7 })).toBe(false)
    expect(isTalentExportPayload({ ...exported, websimExportCode: '' })).toBe(false)
    expect(isTalentExportPayload({ ...exported, talentSchemaRevision: '' })).toBe(false)
    expect(isTalentExportPayload({ ...exported, validation: { ...validation, blockers: 7 } })).toBe(false)
    expect(isTalentImportPayload({ ...imported, rawImportCode: 7 })).toBe(false)
    expect(isTalentImportPayload({ ...imported, talentState: { selectedNodes: [{}] } })).toBe(false)
    expect(isTalentImportPayload({ ...imported, talentSchemaRevision: null })).toBe(false)
  })

  it('returns a complete blocked fallback when a runtime response fails validation', async () => {
    const client = createWebsimClient(responseTransport({ ...validation, blockers: [7] }))
    const result = await client.talentValidate({
      classKey: 'mage',
      specKey: 'frost',
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
    })

    expect(result.fromFallback).toBe(true)
    expect(result.payload).toMatchObject({
      classKey: 'mage',
      specKey: 'frost',
      heroKey: '',
      status: 'failed',
      blockers: ['talent validation service unavailable'],
    })
  })

  it('posts typed validate, export, and import requests to the existing backend contracts', async () => {
    const calls: Array<{ endpoint: string; path: string; data: unknown }> = []
    const responses = [validation, exported, imported]
    const transport: ApiTransport = {
      request: async (_path, options) => ({ payload: options.fallback(), fromFallback: true, error: '' }),
      requestEndpoint: async (endpoint, path, options) => {
        calls.push({ endpoint, path, data: options.data })
        const response = responses.shift()
        return options.validate?.(response)
          ? { payload: response as never, fromFallback: false, error: '' }
          : { payload: options.fallback(), fromFallback: true, error: 'invalid response payload' }
      },
    }
    const client = createWebsimClient(transport)
    const intent = {
      classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
    }

    await client.talentValidate(intent)
    await client.talentExport(intent)
    await client.talentImportCode({ code: 'websim:mage:frost:frostfire:root:1' })

    expect(calls).toEqual([
      { endpoint: 'talents.validate', path: '/api/talents/validate', data: intent },
      { endpoint: 'talents.export', path: '/api/talents/export', data: intent },
      {
        endpoint: 'talents.import', path: '/api/talents/import',
        data: { code: 'websim:mage:frost:frostfire:root:1' },
      },
    ])
  })
})
