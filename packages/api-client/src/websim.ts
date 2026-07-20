import type {
  CommunityTemplateReference,
  CommunityTemplateImportEnvelope,
  GearSlotDefinition,
  GearResultEnvelope,
  GearSelectionIntent,
  GearStatSignature,
  GearStatSnapshotEnvelope,
  GearStatsPayload,
  TalentApiExportPayload,
  TalentApiImportPayload,
  TalentEditRequest,
  TalentImportCodeRequest,
  TalentImportPayload,
  TalentNode,
  TalentNodeAvailabilityPayload,
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
  const heroKey = cleanString(value['heroKey'])
  const row = finiteNumber(value['row'])
  const column = finiteNumber(value['column']) ?? finiteNumber(value['col'])
  const spellId = finiteNumber(value['spellId'])
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
    ...(heroKey ? { heroKey } : {}),
    ...(row !== undefined ? { row } : {}),
    ...(column !== undefined ? { column } : {}),
    ...(spellId !== undefined ? { spellId: Math.trunc(spellId) } : {}),
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

function visualTalentSlotKey(node: TalentNode): string {
  if (
    node.choiceGroup
    || node.nodeType === 2
    || node.shape === 'choice'
    || !node.treeKey
    || node.row === undefined
    || node.column === undefined
  ) return ''
  return [node.treeKey, node.heroKey ?? '', node.row, node.column].join(':')
}

function dedupeVisibleTalentNodes(nodes: readonly TalentNode[]): readonly TalentNode[] {
  const seen = new Set<string>()
  return nodes.filter((node) => {
    const slotKey = visualTalentSlotKey(node)
    if (!slotKey) return true
    if (seen.has(slotKey)) return false
    seen.add(slotKey)
    return true
  })
}

export function normalizeTalentNodeAvailability(value: unknown): TalentNodeAvailabilityPayload | null {
  if (!isRecord(value)) return null
  const schemaRevision = cleanString(value['schemaRevision'])
  const source = cleanString(value['source'])
  const rawNodes = value['nodes']
  if (!schemaRevision || !source || !isRecord(rawNodes)) return null

  const entries: Array<[string, TalentNodeAvailabilityPayload['nodes'][string]]> = []
  for (const [nodeId, rawState] of Object.entries(rawNodes)) {
    if (!nodeId.trim() || !isRecord(rawState)) return null
    const state = rawState['state']
    const reasonCode = cleanString(rawState['reasonCode'])
    const reason = cleanString(rawState['reason'])
    if ((state !== 'selected' && state !== 'available' && state !== 'blocked') || !reasonCode || !reason) {
      return null
    }
    entries.push([nodeId, { state, reasonCode, reason }])
  }
  return { schemaRevision, source, nodes: Object.fromEntries(entries) }
}

export function normalizeCommunityTemplateReference(
  value: CommunityTemplateReference,
): CommunityTemplateReference {
  if (!isRecord(value)) return {}
  const selectedNodes = value['talentState']
  const rawSelectedNodes = isRecord(selectedNodes) && Array.isArray(selectedNodes['selectedNodes'])
    ? selectedNodes['selectedNodes']
    : []
  const normalizedSelectedNodes = rawSelectedNodes.flatMap((node) => {
    if (!isRecord(node)) return []
    const id = cleanString(node['id'])
    const rank = finiteNumber(node['rank'])
    return id && rank !== undefined && rank > 0 ? [{ id, rank }] : []
  })
  const talentState = rawSelectedNodes.length > 0 && normalizedSelectedNodes.length === rawSelectedNodes.length
    ? { selectedNodes: normalizedSelectedNodes }
    : undefined
  const score = value['mplusScore']
  const rank = value['mplusRank']
  const strings = [
    'id', 'title', 'name', 'classKey', 'specKey', 'heroKey', 'scenarioKey',
    'rawImportCode', 'importCode', 'talentImport', 'sourceUrl', 'source', 'sourceKey',
    'sourceName', 'status', 'sourceStatus', 'playerName', 'serverName', 'region',
    'freshnessStatus', 'updatedAt', 'analysisWindow',
  ] as const
  return {
    ...value,
    ...Object.fromEntries(strings.map((field) => [field, cleanString(value[field])])),
    ...(talentState ? { talentState } : {}),
    ...(typeof value['canApplyVisual'] === 'boolean' ? { canApplyVisual: value['canApplyVisual'] } : {}),
    ...(typeof value['isStale'] === 'boolean' ? { isStale: value['isStale'] } : {}),
    ...(typeof score === 'number' && Number.isFinite(score) ? { mplusScore: score } : {}),
    ...(typeof rank === 'number' && Number.isFinite(rank) ? { mplusRank: rank } : {}),
  }
}

export function normalizeTalentsPayload(payload: WebsimTalentsPayload): WebsimTalentsPayload {
  const { nodeAvailability: rawAvailability, ...rest } = payload
  const nodeAvailability = normalizeTalentNodeAvailability(rawAvailability)
  const nodes = payload.nodes
    .map((node) => normalizeTalentNode(node))
    .filter((node): node is TalentNode => node !== null)
  return {
    ...rest,
    nodes: dedupeVisibleTalentNodes(nodes),
    communityTemplates: (payload.communityTemplates ?? []).map(normalizeCommunityTemplateReference),
    presets: (payload.presets ?? []).map(normalizeCommunityTemplateReference),
    ...(nodeAvailability ? { nodeAvailability } : {}),
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
    heroKey: request.heroKey ?? '',
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
    heroKey: request.heroKey ?? '',
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
    heroKey: request.heroKey ?? '',
    talentState: { selectedNodes: [] },
  }
  return {
    classKey: editRequest.classKey,
    specKey: editRequest.specKey,
    heroKey: editRequest.heroKey ?? '',
    rawImportCode: request.code,
    talentState: editRequest.talentState,
    validation: fallbackTalentValidation(editRequest),
    talentSchemaRevision: 'websim-talent-rules-v1',
  }
}

function isStringArray(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isTalentSelectionState(value: unknown): boolean {
  return isRecord(value)
    && Array.isArray(value['selectedNodes'])
    && value['selectedNodes'].every((node) => isRecord(node)
      && typeof node['id'] === 'string'
      && node['id'].trim().length > 0
      && typeof node['rank'] === 'number'
      && Number.isInteger(node['rank'])
      && node['rank'] >= 0)
}

function isTalentSelectedCounts(value: unknown): boolean {
  return isRecord(value)
    && ['class', 'spec', 'hero'].every((key) => typeof value[key] === 'number'
      && Number.isInteger(value[key])
      && (value[key] as number) >= 0)
}

function hasTalentSelectionKeys(value: Readonly<Record<string, unknown>>): boolean {
  return typeof value['classKey'] === 'string'
    && typeof value['specKey'] === 'string'
    && typeof value['heroKey'] === 'string'
}

function hasSchemaRevision(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function isTalentValidationPayload(value: unknown): value is TalentValidationPayload {
  return isRecord(value)
    && hasTalentSelectionKeys(value)
    && hasSchemaRevision(value['status'])
    && hasSchemaRevision(value['source'])
    && hasSchemaRevision(value['schemaRevision'])
    && isStringArray(value['errors'])
    && isStringArray(value['warnings'])
    && isStringArray(value['lines'])
    && isStringArray(value['blockers'])
    && isTalentSelectedCounts(value['selectedCounts'])
    && isTalentSelectionState(value['talentState'])
    && (value['talentSchemaRevision'] === undefined || hasSchemaRevision(value['talentSchemaRevision']))
    && (value['nodeAvailability'] === undefined || normalizeTalentNodeAvailability(value['nodeAvailability']) !== null)
}

export function isTalentExportPayload(value: unknown): value is TalentApiExportPayload {
  return isRecord(value)
    && hasTalentSelectionKeys(value)
    && typeof value['websimExportCode'] === 'string'
    && hasSchemaRevision(value['talentSchemaRevision'])
    && isTalentSelectionState(value['talentState'])
    && isTalentValidationPayload(value['validation'])
}

export function isTalentImportPayload(value: unknown): value is TalentApiImportPayload {
  return isRecord(value)
    && hasTalentSelectionKeys(value)
    && (value['rawImportCode'] === undefined || typeof value['rawImportCode'] === 'string')
    && hasSchemaRevision(value['talentSchemaRevision'])
    && isTalentSelectionState(value['talentState'])
    && isTalentValidationPayload(value['validation'])
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
  profileContext: Readonly<Record<string, unknown>>
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

function fallbackGearStatSnapshotEnvelope(): GearStatSnapshotEnvelope {
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

function isGearProfileReadiness(value: unknown): boolean {
  return isRecord(value)
    && typeof value['status'] === 'string'
    && typeof value['simcReady'] === 'boolean'
    && Array.isArray(value['requiredSlots'])
    && value['requiredSlots'].every((slot) => typeof slot === 'string' && Boolean(slot))
    && Array.isArray(value['readySlots'])
    && value['readySlots'].every((slot) => typeof slot === 'string' && Boolean(slot))
}

function isGearResolveEnvelope(value: unknown): boolean {
  if (!isStructuredEnvelope(value, 'gear-result-envelope-v1')
    || !isRecord(value)
    || !Array.isArray(value['problems'])
    || !value['problems'].every(isRecord)) return false

  const data = value['data']
  if (!isRecord(data)) return false
  if (Object.keys(data).length === 0) {
    return (value['status'] === 'blocked' || value['status'] === 'unavailable') && value['problems'].length > 0
  }
  return data['contractRevision'] === 'gear-resolved-snapshot-v1'
    && typeof data['status'] === 'string'
    && isGearProfileReadiness(data['profileReadiness'])
}

const statSignaturePattern = /^stat-snapshot:sha256:[0-9a-f]{64}$/

function isStatSignature(value: unknown): value is GearStatSignature {
  return typeof value === 'string' && statSignaturePattern.test(value)
}

function isGearStatSnapshotEnvelope(
  value: unknown,
  request: GearStatSnapshotRequest,
): value is GearStatSnapshotEnvelope {
  if (!isRecord(value)
    || value['contractRevision'] !== 'gear-result-envelope-v1'
    || typeof value['requestId'] !== 'string'
    || !value['requestId']
    || !isRecord(value['releaseContext'])
    || !isRecord(value['data'])
    || !Array.isArray(value['problems'])
    || !value['problems'].every(isRecord)) return false

  const eligibility = request.selectionIntent.eligibilityContext
  const expectedClassKey = eligibility?.classKey
  const expectedSpecKey = eligibility?.specKey
  const contextClassKey = request.profileContext['classKey']
  const contextSpecKey = request.profileContext['specKey']
  if (typeof expectedClassKey !== 'string'
    || !expectedClassKey
    || typeof expectedSpecKey !== 'string'
    || !expectedSpecKey
    || (contextClassKey !== undefined && contextClassKey !== expectedClassKey)
    || (contextSpecKey !== undefined && contextSpecKey !== expectedSpecKey)) return false

  const data = value['data']
  if (value['status'] === 'pending') {
    return isStatSignature(data['statSignature'])
      && typeof data['retryAfterMs'] === 'number'
      && Number.isInteger(data['retryAfterMs'])
      && data['retryAfterMs'] > 0
  }
  if (value['status'] === 'resolved') {
    const snapshot = data['statSnapshot']
    return isStatSignature(data['statSignature'])
      && isRecord(snapshot)
      && snapshot['schemaRevision'] === 'gear-stat-snapshot-v1'
      && snapshot['statStatus'] === 'verified'
      && snapshot['statSignature'] === data['statSignature']
      && snapshot['classKey'] === expectedClassKey
      && snapshot['specKey'] === expectedSpecKey
      && Array.isArray(snapshot['blockers'])
      && snapshot['blockers'].every((item) => typeof item === 'string')
      && Array.isArray(snapshot['secondary'])
      && snapshot['secondary'].every(isRecord)
  }
  return value['status'] === 'blocked' || value['status'] === 'unavailable'
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
  gearStatSnapshot(request: GearStatSnapshotRequest): Promise<ApiResult<GearStatSnapshotEnvelope>>
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
        validate: isTalentExportPayload,
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
        validate: isTalentImportPayload,
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
        validate: isGearResolveEnvelope,
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
        fallback: fallbackGearStatSnapshotEnvelope,
        validate: (value) => isGearStatSnapshotEnvelope(value, request),
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
