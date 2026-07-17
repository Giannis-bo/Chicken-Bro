const { requestJson } = require('../common/api-client')

const canonicalGearSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'
]

const gearSlotLabels = {
  head: '头部',
  neck: '颈部',
  shoulder: '肩部',
  back: '披风',
  chest: '胸部',
  wrist: '手腕',
  hands: '手',
  waist: '腰部',
  legs: '腿部',
  feet: '脚',
  finger1: '戒指 1',
  finger2: '戒指 2',
  trinket1: '饰品 1',
  trinket2: '饰品 2',
  main_hand: '主手',
  off_hand: '副手'
}

function fallbackGearSlots() {
  return canonicalGearSlots.map((slot) => ({
    slot,
    simcSlot: slot,
    label: gearSlotLabels[slot] || slot
  }))
}

function fallbackGearSlotGroups() {
  return fallbackGearSlots().map((slot) => ({
    ...slot,
    items: []
  }))
}

function fallbackGearSlotReadiness() {
  return canonicalGearSlots.reduce((readiness, slot) => {
    readiness[slot] = {
      slot,
      label: gearSlotLabels[slot] || slot,
      status: 'blocked',
      simcReady: false,
      missingFields: ['backend'],
      reason: 'backend unavailable'
    }
    return readiness
  }, {})
}

function fallbackWebsimBootstrap() {
  return {
    navTitle: 'WebSim',
    classes: [],
    scenarios: [],
    gearSlots: [],
    defaultSelection: { classKey: 'mage', specKey: 'frost' },
    currentSeason: {
      dataStatus: 'blocked',
      errors: ['missing api base url']
    },
    dataStatus: 'blocked'
  }
}

function fallbackWebsimTalents(params) {
  const options = params || {}
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    heroKey: options.heroKey || '',
    nodes: [],
    treeSections: [],
    presets: [],
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'missing_credentials',
      sources: {},
      templates: { total: 0, verified: 0, blocked: 0 }
    },
    talentStatus: 'blocked',
    currentSeason: {
      dataStatus: 'blocked',
      errors: ['missing api base url']
    },
    errors: ['missing api base url']
  }
}

function fallbackWebsimProfile() {
  return {
    profile: '',
    profileStatus: 'blocked',
    talentEncoding: {
      status: 'failed',
      lines: [],
      errors: ['backend unavailable']
    }
  }
}

function fallbackWebsimGear(params) {
  const options = params || {}
  const slots = fallbackGearSlots()
  const slotGroups = fallbackGearSlotGroups()
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    slots,
    slotGroups,
    baselineSet: [],
    equippedSet: {},
    slotReadiness: fallbackGearSlotReadiness(),
    replacementCandidates: slotGroups,
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'missing_credentials',
      sources: {},
      templates: { total: 0, verified: 0, partial: 0, blocked: 0 },
      checkedAt: ''
    },
    readiness: {
      fullReady: false,
      simcReadyCount: 0,
      selectedCount: 0,
      candidateCount: 0,
      missingRequiredSlots: canonicalGearSlots,
      missingCoreSlots: canonicalGearSlots.filter((slot) => slot !== 'off_hand'),
      requiredReadyCount: canonicalGearSlots.length - 1,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
      warnings: ['backend unavailable']
    },
    statSnapshot: fallbackWebsimGearStats(options),
    gearSchemaRevision: 'websim-gear-simulator-v1',
    gearCatalogRevision: 'websim-gear-catalog-v1',
    catalogStatus: 'blocked',
    itemDatabaseRevision: '',
    variantRevision: '',
    catalogCheckedAt: '',
    catalogBlockers: ['backend unavailable'],
    maxLevel: 0,
    checkedAt: '',
    dataStatus: 'blocked'
  }
}

function fallbackWebsimGearStats(params) {
  const options = params || {}
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    statStatus: 'blocked',
    blockers: ['backend unavailable'],
    primary: null,
    stamina: null,
    secondary: [],
    armor: null,
    weaponDps: null,
    itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
    gearReadiness: {
      fullReady: false,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
      warnings: ['backend unavailable']
    },
    talentEncoding: {
      status: 'failed',
      lines: [],
      errors: ['backend unavailable']
    },
    gearSchemaRevision: 'websim-gear-simulator-v1',
    maxLevel: 0,
    checkedAt: ''
  }
}

function requestWebsimBootstrap() {
  return requestJson('/api/websim/bootstrap', {
    fallback: fallbackWebsimBootstrap,
    validate: (data) => data && Array.isArray(data.classes)
  })
}

function requestWebsimTalents(params) {
  const options = params || {}
  const query = [
    `class=${encodeURIComponent(options.classKey || '')}`,
    `spec=${encodeURIComponent(options.specKey || '')}`
  ]
  if (options.heroKey) query.push(`hero=${encodeURIComponent(options.heroKey)}`)
  return requestJson(`/api/websim/talents?${query.join('&')}`, {
    fallback: () => fallbackWebsimTalents(options),
    validate: (data) => data && Array.isArray(data.nodes) && Array.isArray(data.treeSections)
  })
}

function fallbackWebsimTalentImport(params) {
  const options = params || {}
  const talents = fallbackWebsimTalents(options)
  const template = (talents.communityTemplates || []).find((item) => item && (item.rawImportCode || item.importCode || item.talentImport))
  return {
    classKey: options.classKey || '',
    specKey: options.specKey || '',
    heroKey: options.heroKey || '',
    importCode: template ? (template.rawImportCode || template.importCode || template.talentImport || '') : '',
    source: 'community_template',
    status: template ? 'verified' : 'blocked',
    blockers: template ? [] : ['no SimC-ready community talent import']
  }
}

function requestWebsimTalentImport(params) {
  const options = params || {}
  const query = [
    `class=${encodeURIComponent(options.classKey || '')}`,
    `spec=${encodeURIComponent(options.specKey || '')}`
  ]
  if (options.heroKey) query.push(`hero=${encodeURIComponent(options.heroKey)}`)
  return requestJson(`/api/websim/talents/import?${query.join('&')}`, {
    timeout: 30000,
    fallback: () => fallbackWebsimTalentImport(options),
    validate: (data) => data && typeof data.importCode === 'string' && data.status
  })
}

function requestWebsimProfile(payload) {
  return requestJson('/api/websim/profile', {
    method: 'POST',
    data: payload || {},
    timeout: 30000,
    fallback: fallbackWebsimProfile,
    validate: (data) => data && data.talentEncoding
  })
}

function isGearResultEnvelope(data) {
  return !!(data && data.contractRevision === 'gear-result-envelope-v1')
}

function requestWebsimGearResolve(selectionIntent) {
  return requestJson('/api/websim/gear/resolve', {
    method: 'POST',
    data: selectionIntent || {},
    timeout: 30000,
    responseMode: 'structured-problem',
    fallback: () => null,
    validate: isGearResultEnvelope
  })
}

function requestWebsimGearAttributeAudit(selectionIntent, characterContext) {
  return requestJson('/api/websim/gear/attributes', {
    method: 'POST',
    data: {
      selectionIntent: selectionIntent || {},
      characterContext: characterContext || {}
    },
    timeout: 6000,
    responseMode: 'structured-problem',
    fallback: () => null,
    validate: isGearResultEnvelope
  })
}

function requestWebsimCommunityTemplateImport(params) {
  const source = params || {}
  const data = {
    classKey: String(source.classKey || ''),
    specKey: String(source.specKey || ''),
    templateId: String(source.templateId || ''),
    expectedManifestRevision: String(source.expectedManifestRevision || '')
  }
  return requestJson('/api/websim/gear/community-import', {
    method: 'POST',
    data,
    timeout: 30000,
    responseMode: 'structured-problem',
    fallback: () => null,
    validate: (value) => value && value.contractRevision === 'community-template-import-envelope-v1'
  })
}

function requestWebsimProfileFromIntent(selectionIntent, profileContext) {
  return requestJson('/api/websim/profile', {
    method: 'POST',
    data: {
      selectionIntent: selectionIntent || {},
      profileContext: profileContext || {}
    },
    timeout: 30000,
    responseMode: 'structured-problem',
    fallback: () => null,
    validate: isGearResultEnvelope
  })
}

function requestWebsimGearStatSnapshot(selectionIntent, profileContext, options) {
  const timeoutMs = Math.min(30000, Math.max(1, Number(options && options.timeoutMs) || 30000))
  return requestJson('/api/websim/gear/stat-snapshots', {
    method: 'POST',
    data: {
      selectionIntent: selectionIntent || {},
      profileContext: profileContext || {}
    },
    timeout: timeoutMs,
    responseMode: 'structured-problem',
    fallback: () => null,
    validate: isGearResultEnvelope
  })
}

function requestWebsimGear(params) {
  const options = params || {}
  const query = [
    `class=${encodeURIComponent(options.classKey || '')}`,
    `spec=${encodeURIComponent(options.specKey || '')}`
  ]
  if (options.compact !== false) query.push('compact=1')
  if (options.mode) query.push(`mode=${encodeURIComponent(options.mode)}`)
  if (options.slot) query.push(`slot=${encodeURIComponent(options.slot)}`)
  return requestJson(`/api/websim/gear?${query.join('&')}`, {
    timeout: 30000,
    fallback: () => fallbackWebsimGear(options),
    validate: (data) => data && Array.isArray(data.slots) && data.equippedSet && data.readiness
  })
}

function requestWebsimGearStats(payload) {
  const source = payload || {}
  return requestJson('/api/websim/gear/stats', {
    method: 'POST',
    data: source,
    timeout: 60000,
    fallback: () => fallbackWebsimGearStats(source),
    validate: (data) => data && data.statStatus && Array.isArray(data.blockers)
  })
}

module.exports = {
  fallbackWebsimBootstrap,
  fallbackWebsimGear,
  fallbackWebsimGearStats,
  fallbackWebsimProfile,
  fallbackWebsimTalentImport,
  fallbackWebsimTalents,
  requestWebsimBootstrap,
  requestWebsimCommunityTemplateImport,
  requestWebsimGear,
  requestWebsimGearAttributeAudit,
  requestWebsimGearResolve,
  requestWebsimGearStatSnapshot,
  requestWebsimGearStats,
  requestWebsimProfile,
  requestWebsimProfileFromIntent,
  requestWebsimTalentImport,
  requestWebsimTalents
}
