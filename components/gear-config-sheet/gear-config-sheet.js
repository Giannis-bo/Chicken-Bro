const STATUS_LABELS = {
  ready: '可应用',
  ready_to_simulate: '可应用',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  loading: '读取中',
  unknown: '未知'
}

const STATUS_GLYPHS = {
  ready: 'OK',
  ready_to_simulate: 'OK',
  verified: 'OK',
  blocked: '!',
  partial: '!',
  stale: '刷',
  source_reference: '源',
  loading: '读',
  unknown: '?'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function normalizeStatus(value) {
  const status = cleanText(value, 'source_reference')
  if (status === 'ready') return status
  if (status === 'ready_to_simulate') return status
  if (status === 'verified') return status
  if (status === 'blocked') return status
  if (status === 'partial') return status
  if (status === 'stale') return status
  if (status === 'loading') return status
  if (status === 'source_reference') return status
  return 'source_reference'
}

function statusLabel(status, fallback) {
  return cleanText(fallback, STATUS_LABELS[status] || STATUS_LABELS.source_reference)
}

function statusGlyph(status, fallback) {
  return cleanText(fallback, STATUS_GLYPHS[status] || STATUS_GLYPHS.source_reference)
}

function normalizeChip(option, index, fallbackPrefix) {
  const status = normalizeStatus(option.status || option.state)
  return {
    key: cleanText(option.key || option.id || option.value, `${fallbackPrefix}-${index}`),
    label: cleanText(option.label || option.title, '选项'),
    meta: cleanText(option.meta || option.desc || option.sourceLabel),
    status,
    statusLabel: statusLabel(status, option.statusLabel),
    selected: Boolean(option.selected || option.active)
  }
}

function normalizeCandidate(candidate, index, selectedCandidateId) {
  const status = normalizeStatus(candidate.status || candidate.state)
  const id = cleanText(candidate.id || candidate.key || candidate.itemId, `candidate-${index}`)
  const title = cleanText(candidate.title || candidate.itemName || candidate.name, '装备候选')
  return {
    id,
    title,
    meta: cleanText(candidate.meta || candidate.sourceLabel || candidate.itemLevelLabel, '来源待读取'),
    detail: cleanText(candidate.detail || candidate.reason || candidate.desc),
    iconSrc: cleanText(candidate.iconSrc || candidate.iconUrl),
    iconName: cleanText(candidate.iconName),
    fallbackText: cleanText(candidate.fallbackText || candidate.iconText || title, '装').slice(0, 2),
    status,
    statusLabel: statusLabel(status, candidate.statusLabel),
    statusGlyph: statusGlyph(status, candidate.statusGlyph),
    selected: selectedCandidateId && selectedCandidateId === id,
    disabled: Boolean(candidate.disabled)
  }
}

function normalizeRows(rows, fallbackPrefix) {
  return normalizeArray(rows).map((row, index) => {
    const status = normalizeStatus(row.status || row.state)
    return {
      key: cleanText(row.key || row.id, `${fallbackPrefix}-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value: cleanText(row.value || row.desc, '待读取'),
      status,
      statusLabel: statusLabel(status, row.statusLabel)
    }
  })
}

function normalizeAction(action, fallbackLabel, fallbackTone) {
  const data = action || {}
  return {
    key: cleanText(data.key || data.actionKey),
    label: cleanText(data.label, fallbackLabel),
    tone: cleanText(data.tone, fallbackTone),
    disabled: Boolean(data.disabled),
    loading: Boolean(data.loading)
  }
}

function buildState(data) {
  const status = normalizeStatus(data.applyState || data.state)
  const selectedCandidateId = cleanText(data.selectedCandidateId)
  const candidates = normalizeArray(data.candidates).map((candidate, index) => normalizeCandidate(candidate, index, selectedCandidateId))
  const evidenceRows = normalizeRows(data.evidenceRows, 'gear-sheet-evidence')
  return {
    rootClass: `state-${status}${data.visible ? ' is-visible' : ' is-hidden'}`,
    normalizedStatus: status,
    normalizedStateLabel: statusLabel(status, data.stateLabel),
    normalizedStateGlyph: statusGlyph(status, data.stateGlyph),
    normalizedSourceFilters: normalizeArray(data.sourceFilters).map((filter, index) => normalizeChip(filter, index, 'source')),
    normalizedCandidates: candidates,
    normalizedCandidateCountLabel: `${candidates.length} 个候选`,
    normalizedVariantTracks: normalizeArray(data.variantTracks).map((option, index) => normalizeChip(option, index, 'variant')),
    normalizedCraftedStatOptions: normalizeArray(data.craftedStatOptions).map((option, index) => normalizeChip(option, index, 'crafted')),
    normalizedSocketOptions: normalizeArray(data.socketOptions).map((option, index) => normalizeChip(option, index, 'socket')),
    normalizedEnchantOptions: normalizeArray(data.enchantOptions).map((option, index) => normalizeChip(option, index, 'enchant')),
    normalizedEmbellishmentOptions: normalizeArray(data.embellishmentOptions).map((option, index) => normalizeChip(option, index, 'embellishment')),
    normalizedCommunityTemplates: normalizeArray(data.communityTemplates).map((option, index) => normalizeChip(option, index, 'community')),
    normalizedBlockerRows: normalizeRows(data.blockers, 'blocker'),
    normalizedEvidenceRows: evidenceRows,
    normalizedEvidenceSummary: `${evidenceRows.length} 条证据`,
    normalizedApplyAction: normalizeAction(data.applyAction, status === 'ready' || status === 'ready_to_simulate' ? '应用装备' : '暂不可应用', status === 'blocked' ? 'danger' : 'primary'),
    normalizedCloseAction: normalizeAction(data.closeAction, '关闭', 'ghost')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    visible: { type: Boolean, value: false },
    state: { type: String, value: 'source_reference' },
    applyState: { type: String, value: '' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: '装备配置' },
    meta: { type: String, value: '' },
    slotLabel: { type: String, value: '槽位' },
    selectedCandidateId: { type: String, value: '' },
    sourceFilters: { type: Array, value: [] },
    candidates: { type: Array, value: [] },
    variantTracks: { type: Array, value: [] },
    craftedStatOptions: { type: Array, value: [] },
    socketOptions: { type: Array, value: [] },
    enchantOptions: { type: Array, value: [] },
    embellishmentOptions: { type: Array, value: [] },
    communityTemplates: { type: Array, value: [] },
    blockers: { type: Array, value: [] },
    evidenceRows: { type: Array, value: [] },
    applyAction: { type: Object, value: {} },
    closeAction: { type: Object, value: {} }
  },
  data: buildState({}),
  observers: {
    'visible, state, applyState, stateLabel, stateGlyph, selectedCandidateId, sourceFilters, candidates, variantTracks, craftedStatOptions, socketOptions, enchantOptions, embellishmentOptions, communityTemplates, blockers, evidenceRows, applyAction, closeAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleCloseTap() {
      this.triggerEvent('close', this.data.normalizedCloseAction)
    },
    handleSourceTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('filterchange', { key: dataset.key || '' })
    },
    handleCandidateTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('candidatepick', { candidateId: dataset.id || '', status: dataset.status || '' })
    },
    handleVariantTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('variantpick', { key: dataset.key || '', status: dataset.status || '' })
    },
    handleCraftedTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('craftedpick', { key: dataset.key || '', status: dataset.status || '' })
    },
    handleEnhancementTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('enhancementpick', {
        kind: dataset.kind || '',
        key: dataset.key || '',
        status: dataset.status || ''
      })
    },
    handleCommunityTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('communitytap', { key: dataset.key || '', status: dataset.status || '' })
    },
    handleApplyTap() {
      this.triggerEvent('applytap', this.data.normalizedApplyAction)
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
