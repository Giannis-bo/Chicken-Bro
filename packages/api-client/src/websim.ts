import type {
  CommunityTemplateImportEnvelope,
  GearSlotDefinition,
  GearResultEnvelope,
  GearSelectionIntent,
  GearStatsPayload,
  TalentApiExportPayload,
  TalentApiImportPayload,
  TalentEditRequest,
  TalentImportCodeRequest,
  TalentImportPayload,
  TalentNode,
  TalentValidationPayload,
  WebsimBootstrapPayload,
  WebsimGearPayload,
  WebsimSelection,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

import { cleanString, encodeQuery, isRecord, stringArray } from './guards'
import type { ApiResult, ApiTransport, RequestData } from './transport'

const slotLabels: Readonly<Record<string, string>> = {
  head: '头部', neck: '颈部', shoulder: '肩部', back: '披风', chest: '胸部', wrist: '手腕',
  hands: '手', waist: '腰部', legs: '腿部', feet: '脚', finger1: '戒指 1', finger2: '戒指 2',
  trinket1: '饰品 1', trinket2: '饰品 2', main_hand: '主手', off_hand: '副手',
}

export const canonicalGearSlots = Object.keys(slotLabels)

function slots(): readonly GearSlotDefinition[] {
  return canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slotLabels[slot] ?? slot }))
}

function fallbackBootstrap(): WebsimBootstrapPayload {
  return {
    navTitle: 'WebSim', classes: [], scenarios: [], gearSlots: [],
    defaultSelection: { classKey: 'mage', specKey: 'frost' },
    currentSeason: { dataStatus: 'blocked', errors: ['missing api base url'] },
    dataStatus: 'blocked',
  }
}

function fallbackTalents(selection: WebsimSelection): WebsimTalentsPayload {
  return {
    classKey: selection.classKey,
    specKey: selection.specKey,
    ...(selection.heroKey ? { heroKey: selection.heroKey } : {}),
    nodes: [], treeSections: [], presets: [], communityTemplates: [], talentStatus: 'blocked',
    currentSeason: { dataStatus: 'blocked', errors: ['missing api base url'] },
    errors: ['missing api base url'],
  }
}

function finiteNumber(value: unknown): number | undefined {
  if (typeof value !== 'number' && typeof value !== 'string') return undefined
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : undefined
}

export function normalizeTalentNode(value: unknown): TalentNode | null {
  if (!isRecord(value)) return null
  const id = cleanString(value['id'])
  const name = cleanString(value['name'])
  if (!id || !name) return null

  const treeType = cleanString(value['treeType'])
  const treeKey = cleanString(value['treeKey']) || treeType
  const row = finiteNumber(value['row'])
  const column = finiteNumber(value['column']) ?? finiteNumber(value['col'])
  const selectedRank = finiteNumber(value['ranks']) ?? finiteNumber(value['selectedRank']) ?? 0
  const maxRank = finiteNumber(value['maxRank']) ?? finiteNumber(value['rankCount']) ?? 1
  const requiredPoints = finiteNumber(value['requiredPoints']) ?? finiteNumber(value['pointRequirement'])
  const grantedRank = finiteNumber(value['grantedRank'])
  const nodeType = finiteNumber(value['nodeType'])
  const prerequisiteIds = stringArray(value['prerequisiteIds']).length
    ? stringArray(value['prerequisiteIds'])
    : stringArray(value['parentIds'])
  const choiceOptions = Array.isArray(value['choiceOptions'])
    ? value['choiceOptions']
      .map(normalizeTalentNode)
      .filter((node): node is TalentNode => node !== null)
    : []

  return {
    id,
    name,
    ...(cleanString(value['key']) ? { key: cleanString(value['key']) } : {}),
    ...(cleanString(value['description']) ? { description: cleanString(value['description']) } : {}),
    ...(cleanString(value['descriptionStatus']) ? { descriptionStatus: cleanString(value['descriptionStatus']) } : {}),
    ...(treeKey ? { treeKey } : {}),
    ...(treeType ? { treeType } : {}),
    ...(row !== undefined ? { row } : {}),
    ...(column !== undefined ? { column } : {}),
    maxRank: Math.max(1, Math.trunc(maxRank)),
    ranks: Math.max(0, Math.trunc(selectedRank)),
    ...(grantedRank !== undefined ? { grantedRank: Math.max(0, Math.trunc(grantedRank)) } : {}),
    ...(requiredPoints !== undefined ? { requiredPoints: Math.max(0, Math.trunc(requiredPoints)) } : {}),
    ...(prerequisiteIds.length ? { prerequisiteIds } : {}),
    ...(cleanString(value['parentMode']) ? { parentMode: cleanString(value['parentMode']) } : {}),
    ...(cleanString(value['choiceGroup']) ? { choiceGroup: cleanString(value['choiceGroup']) } : {}),
    ...(nodeType !== undefined ? { nodeType: Math.trunc(nodeType) } : {}),
    ...(cleanString(value['shape']) ? { shape: cleanString(value['shape']) } : {}),
    ...(typeof value['granted'] === 'boolean' ? { granted: value['granted'] } : {}),
    ...(choiceOptions.length ? { choiceOptions } : {}),
    ...(cleanString(value['iconUrl']) ? { iconUrl: cleanString(value['iconUrl']) } : {}),
    ...(cleanString(value['sourceUrl']) ? { sourceUrl: cleanString(value['sourceUrl']) } : {}),
  }
}

export function normalizeTalentsPayload(payload: WebsimTalentsPayload): WebsimTalentsPayload {
  return {
    ...payload,
    nodes: payload.nodes
      .map((node) => normalizeTalentNode(node))
      .filter((node): node is TalentNode => node !== null),
  }
}

function fallbackTalentImport(selection: WebsimSelection): TalentImportPayload {
  return {
    classKey: selection.classKey,
    specKey: selection.specKey,
    ...(selection.heroKey ? { heroKey: selection.heroKey } : {}),
    importCode: '', source: 'community_template', status: 'blocked',
    blockers: ['no SimC-ready community talent import'],
  }
}

function fallbackTalentValidation(request: TalentEditRequest): TalentValidationPayload {
  return {
    classKey: request.classKey,
    specKey: request.specKey,
    ...(request.heroKey ? { heroKey: request.heroKey } : {}),
    status: 'failed',
    source: 'transport_fallback',
    schemaRevision: 'websim-talent-rules-v1',
    errors: ['talent validation service unavailable'],
    warnings: [],
    lines: [],
    selectedCounts: { class: 0, spec: 0, hero: 0 },
    talentState: request.talentState,
    talentSchemaRevision: 'websim-talent-rules-v1',
    blockers: ['talent validation service unavailable'],
  }
}

function fallbackTalentExport(request: TalentEditRequest): TalentApiExportPayload {
  return {
    classKey: request.classKey,
    specKey: request.specKey,
    ...(request.heroKey ? { heroKey: request.heroKey } : {}),
    talentState: request.talentState,
    websimExportCode: '',
    validation: fallbackTalentValidation(request),
    talentSchemaRevision: 'websim-talent-rules-v1',
  }
}

function fallbackTalentCodeImport(request: TalentImportCodeRequest): TalentApiImportPayload {
  const editRequest: TalentEditRequest = {
    classKey: request.classKey ?? '',
    specKey: request.specKey ?? '',
    ...(request.heroKey ? { heroKey: request.heroKey } : {}),
    talentState: { selectedNodes: [] },
  }
  return {
    classKey: editRequest.classKey,
    specKey: editRequest.specKey,
    ...(editRequest.heroKey ? { heroKey: editRequest.heroKey } : {}),
    rawImportCode: request.code,
    talentState: editRequest.talentState,
    validation: fallbackTalentValidation(editRequest),
    talentSchemaRevision: 'websim-talent-rules-v1',
  }
}

function isTalentValidationPayload(value: unknown): value is TalentValidationPayload {
  return isRecord(value)
    && typeof value['status'] === 'string'
    && Array.isArray(value['errors'])
    && Array.isArray(value['warnings'])
    && Array.isArray(value['lines'])
    && isRecord(value['selectedCounts'])
    && isRecord(value['talentState'])
    && Array.isArray(value['talentState']['selectedNodes'])
}

function fallbackStats(selection: WebsimSelection): GearStatsPayload {
  return {
    classKey: selection.classKey,
    specKey: selection.specKey,
    ...(selection.heroKey ? { heroKey: selection.heroKey } : {}),
    statStatus: 'blocked', blockers: ['backend unavailable'], primary: null, stamina: null,
    secondary: [], armor: null, weaponDps: null,
    itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
    gearReadiness: { fullReady: false, warnings: ['backend unavailable'] },
    talentEncoding: { status: 'failed', lines: [], errors: ['backend unavailable'] },
    checkedAt: '',
  }
}

function fallbackGear(selection: WebsimSelection): WebsimGearPayload {
  const definitions = slots()
  const slotReadiness = Object.fromEntries(definitions.map((slot) => [slot.slot, {
    slot: slot.slot, label: slot.label, status: 'blocked', simcReady: false,
    missingFields: ['backend'], reason: 'backend unavailable',
  }]))
  const groups = definitions.map((slot) => ({ ...slot, items: [] }))
  return {
    classKey: selection.classKey,
    specKey: selection.specKey,
    ...(selection.heroKey ? { heroKey: selection.heroKey } : {}),
    slots: definitions, slotGroups: groups, equippedSet: {}, slotReadiness,
    replacementCandidates: groups, communityTemplates: [],
    readiness: {
      fullReady: false, simcReadyCount: 0, selectedCount: 0, candidateCount: 0,
      missingRequiredSlots: canonicalGearSlots, missingCoreSlots: canonicalGearSlots.filter((slot) => slot !== 'off_hand'),
      requiredReadyCount: canonicalGearSlots.length - 1,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
      warnings: ['backend unavailable'],
    },
    statSnapshot: fallbackStats(selection), catalogStatus: 'blocked',
    catalogBlockers: ['backend unavailable'], checkedAt: '', dataStatus: 'blocked',
  }
}

export interface GearRequest extends WebsimSelection {
  compact?: boolean
  mode?: string
  slot?: string
}

export interface CommunityTemplateImportRequest extends WebsimSelection {
  templateId: string
  expectedManifestRevision?: string
}

export interface GearStatSnapshotRequest {
  selectionIntent: GearSelectionIntent
  profileContext: RequestData
  timeoutMs?: number
}

function fallbackGearEnvelope(): GearResultEnvelope {
  return {
    contractRevision: 'gear-result-envelope-v1',
    requestId: 'transport-fallback',
    status: 'unavailable',
    releaseContext: {},
    data: {},
    problems: [{ kind: 'TRANSPORT_ERROR', code: 'GEAR_TRANSPORT_UNAVAILABLE', retryable: true }],
  }
}

function fallbackCommunityImportEnvelope(): CommunityTemplateImportEnvelope {
  return {
    contractRevision: 'community-template-import-envelope-v1',
    requestId: 'transport-fallback',
    status: 'unavailable',
    releaseContext: {},
    data: {},
    problems: [{ kind: 'TRANSPORT_ERROR', code: 'GEAR_TRANSPORT_UNAVAILABLE', retryable: true }],
  }
}

function isStructuredEnvelope(value: unknown, contractRevision: string): boolean {
  return isRecord(value)
    && value['contractRevision'] === contractRevision
    && typeof value['requestId'] === 'string'
    && typeof value['status'] === 'string'
    && isRecord(value['releaseContext'])
    && isRecord(value['data'])
    && Array.isArray(value['problems'])
}

export interface WebsimClient {
  bootstrap(): Promise<ApiResult<WebsimBootstrapPayload>>
  talents(selection: WebsimSelection): Promise<ApiResult<WebsimTalentsPayload>>
  talentImport(selection: WebsimSelection): Promise<ApiResult<TalentImportPayload>>
  talentValidate(request: TalentEditRequest): Promise<ApiResult<TalentValidationPayload>>
  talentExport(request: TalentEditRequest): Promise<ApiResult<TalentApiExportPayload>>
  talentImportCode(request: TalentImportCodeRequest): Promise<ApiResult<TalentApiImportPayload>>
  gear(request: GearRequest): Promise<ApiResult<WebsimGearPayload>>
  gearResolve(selectionIntent: GearSelectionIntent): Promise<ApiResult<GearResultEnvelope>>
  communityTemplateImport(request: CommunityTemplateImportRequest): Promise<ApiResult<CommunityTemplateImportEnvelope>>
  gearStatSnapshot(request: GearStatSnapshotRequest): Promise<ApiResult<GearResultEnvelope>>
  gearStats(payload: RequestData & Partial<WebsimSelection>): Promise<ApiResult<GearStatsPayload>>
}

export function createWebsimClient(transport: ApiTransport): WebsimClient {
  return {
    bootstrap() {
      return transport.requestEndpoint('websim.bootstrap', '/api/websim/bootstrap', {
        fallback: fallbackBootstrap,
        validate: (value) => isRecord(value) && Array.isArray(value['classes']),
      })
    },
    async talents(selection) {
      const query = encodeQuery({ class: selection.classKey, spec: selection.specKey, hero: selection.heroKey })
      const result = await transport.requestEndpoint<WebsimTalentsPayload>('websim.talents', `/api/websim/talents?${query}`, {
        fallback: () => fallbackTalents(selection),
        validate: (value) => isRecord(value) && Array.isArray(value['nodes']) && Array.isArray(value['treeSections']),
      })
      return { ...result, payload: normalizeTalentsPayload(result.payload) }
    },
    talentImport(selection) {
      const query = encodeQuery({ class: selection.classKey, spec: selection.specKey, hero: selection.heroKey })
      return transport.requestEndpoint('websim.talentImport', `/api/websim/talents/import?${query}`, {
        fallback: () => fallbackTalentImport(selection),
        validate: (value) => isRecord(value) && typeof value['importCode'] === 'string' && typeof value['status'] === 'string',
      })
    },
    talentValidate(request) {
      return transport.requestEndpoint('talents.validate', '/api/talents/validate', {
        data: { ...request },
        fallback: () => fallbackTalentValidation(request),
        validate: isTalentValidationPayload,
      })
    },
    talentExport(request) {
      return transport.requestEndpoint('talents.export', '/api/talents/export', {
        data: { ...request },
        fallback: () => fallbackTalentExport(request),
        validate: (value) => isRecord(value)
          && typeof value['websimExportCode'] === 'string'
          && isRecord(value['talentState'])
          && isTalentValidationPayload(value['validation']),
      })
    },
    talentImportCode(request) {
      return transport.requestEndpoint('talents.import', '/api/talents/import', {
        data: {
          code: request.code,
          ...(request.classKey ? { classKey: request.classKey } : {}),
          ...(request.specKey ? { specKey: request.specKey } : {}),
          ...(request.heroKey ? { heroKey: request.heroKey } : {}),
        },
        fallback: () => fallbackTalentCodeImport(request),
        validate: (value) => isRecord(value)
          && isRecord(value['talentState'])
          && isTalentValidationPayload(value['validation']),
      })
    },
    gear(request) {
      const query = encodeQuery({
        class: request.classKey, spec: request.specKey,
        compact: request.compact === false ? undefined : 1,
        mode: request.mode, slot: request.slot,
      })
      return transport.requestEndpoint('websim.gear', `/api/websim/gear?${query}`, {
        fallback: () => fallbackGear(request),
        validate: (value) => isRecord(value)
          && Array.isArray(value['slots'])
          && isRecord(value['equippedSet'])
          && isRecord(value['readiness']),
      })
    },
    gearResolve(selectionIntent) {
      return transport.requestEndpoint('websim.gearResolve', '/api/websim/gear/resolve', {
        data: { ...selectionIntent },
        responseMode: 'structured-problem',
        fallback: fallbackGearEnvelope,
        validate: (value) => isStructuredEnvelope(value, 'gear-result-envelope-v1'),
      })
    },
    communityTemplateImport(request) {
      return transport.requestEndpoint('websim.gearCommunityImport', '/api/websim/gear/community-import', {
        data: {
          classKey: request.classKey,
          specKey: request.specKey,
          templateId: request.templateId,
          expectedManifestRevision: request.expectedManifestRevision ?? '',
        },
        responseMode: 'structured-problem',
        fallback: fallbackCommunityImportEnvelope,
        validate: (value) => isStructuredEnvelope(value, 'community-template-import-envelope-v1'),
      })
    },
    gearStatSnapshot(request) {
      return transport.requestEndpoint('websim.gearStatSnapshots', '/api/websim/gear/stat-snapshots', {
        data: {
          selectionIntent: request.selectionIntent,
          profileContext: request.profileContext,
        },
        timeoutMs: Math.min(30000, Math.max(1, request.timeoutMs ?? 30000)),
        responseMode: 'structured-problem',
        fallback: fallbackGearEnvelope,
        validate: (value) => isStructuredEnvelope(value, 'gear-result-envelope-v1'),
      })
    },
    gearStats(payload) {
      const selection = {
        classKey: typeof payload === 'object' && payload !== null && 'classKey' in payload && typeof payload.classKey === 'string' ? payload.classKey : '',
        specKey: typeof payload === 'object' && payload !== null && 'specKey' in payload && typeof payload.specKey === 'string' ? payload.specKey : '',
      }
      return transport.requestEndpoint('websim.gearStats', '/api/websim/gear/stats', {
        data: payload,
        fallback: () => fallbackStats(selection),
        validate: (value) => isRecord(value) && typeof value['statStatus'] === 'string' && Array.isArray(value['blockers']),
      })
    },
  }
}
