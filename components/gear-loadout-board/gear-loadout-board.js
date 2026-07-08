const STATUS_LABELS = {
  ready_to_simulate: '可提交模拟',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  loading: '读取中',
  missing: '缺失',
  unknown: '未知'
}

const STATUS_GLYPHS = {
  ready_to_simulate: 'OK',
  verified: 'OK',
  blocked: '!',
  partial: '!',
  stale: '刷',
  source_reference: '源',
  loading: '读',
  missing: '缺',
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
  if (status === 'ready_to_simulate') return status
  if (status === 'verified') return status
  if (status === 'blocked') return status
  if (status === 'partial') return status
  if (status === 'stale') return status
  if (status === 'loading') return status
  if (status === 'missing') return status
  if (status === 'source_reference') return status
  return 'source_reference'
}

function statusLabel(status, fallback) {
  return cleanText(fallback, STATUS_LABELS[status] || STATUS_LABELS.source_reference)
}

function statusGlyph(status, fallback) {
  return cleanText(fallback, STATUS_GLYPHS[status] || STATUS_GLYPHS.source_reference)
}

function normalizeSlot(slot, index, selectedSlotId) {
  const status = normalizeStatus(slot.status || slot.slotState || slot.state)
  const slotId = cleanText(slot.slotId || slot.id || slot.key, `slot-${index}`)
  const title = cleanText(slot.itemName || slot.title || slot.name, status === 'missing' ? '未选择装备' : '装备槽')
  const slotLabel = cleanText(slot.slotLabel || slot.label, `槽位 ${index + 1}`)
  const meta = cleanText(slot.meta || slot.sourceLabel || slot.itemLevelLabel || slot.enhancementSummary)
  const iconSrc = cleanText(slot.iconSrc || slot.iconUrl)
  const iconName = cleanText(slot.iconName)
  const fallbackText = cleanText(slot.fallbackText || slot.iconText || slotLabel, '装').slice(0, 2)
  const blockerText = normalizeArray(slot.blockers).map((blocker) => {
    if (typeof blocker === 'string') return blocker
    return cleanText(blocker.title || blocker.label || blocker.value)
  }).filter(Boolean).slice(0, 2).join(' / ')

  return {
    slotId,
    slotLabel,
    title,
    meta,
    iconSrc,
    iconName,
    fallbackText,
    status,
    statusLabel: statusLabel(status, slot.statusLabel),
    statusGlyph: statusGlyph(status, slot.statusGlyph),
    enhancementSummary: cleanText(slot.enhancementSummary),
    blockerText,
    isSelected: selectedSlotId && selectedSlotId === slotId,
    isMissing: status === 'missing' || Boolean(slot.missing),
    canOpenConfig: !slot.disabled
  }
}

function loadingSlots() {
  return [
    '头部', '项链', '肩部', '披风',
    '胸甲', '护腕', '手套', '腰部'
  ].map((label, index) => ({
    slotId: `loading-${index}`,
    slotLabel: label,
    title: '读取中',
    meta: '等待装备来源',
    fallbackText: label.slice(0, 1),
    status: 'loading',
    statusLabel: statusLabel('loading'),
    statusGlyph: statusGlyph('loading'),
    blockerText: '',
    enhancementSummary: '',
    isSelected: false,
    isMissing: false,
    canOpenConfig: false
  }))
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

function normalizeAction(action, fallbackLabel) {
  const data = action || {}
  return {
    key: cleanText(data.key || data.actionKey),
    label: cleanText(data.label, fallbackLabel),
    tone: cleanText(data.tone, 'secondary'),
    disabled: Boolean(data.disabled),
    loading: Boolean(data.loading)
  }
}

function buildState(data) {
  const status = normalizeStatus(data.state)
  const normalizedInputSlots = normalizeArray(data.slots).map((slot, index) => normalizeSlot(slot, index, data.selectedSlotId))
  const slots = normalizedInputSlots.length || status !== 'loading' ? normalizedInputSlots : loadingSlots()
  const evidenceRows = normalizeRows(data.evidenceRows, 'gear-evidence')
  const previewRows = normalizeRows(data.evidencePreviewRows, 'gear-evidence-preview').length
    ? normalizeRows(data.evidencePreviewRows, 'gear-evidence-preview')
    : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${status}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedStatus: status,
    normalizedStateLabel: statusLabel(status, data.stateLabel),
    normalizedStateGlyph: statusGlyph(status, data.stateGlyph),
    normalizedSlots: slots,
    normalizedSlotCountLabel: `${slots.filter((slot) => slot.status !== 'missing').length}/${slots.length || 16} 槽`,
    normalizedStatRows: normalizeRows(data.statSummaryRows, 'stat'),
    normalizedReadinessRows: normalizeRows(data.readinessRows, 'readiness'),
    normalizedEvidenceRows: data.evidenceExpanded ? evidenceRows : previewRows,
    normalizedEvidenceSummary: data.evidenceExpanded ? `${evidenceRows.length} 条证据` : `${previewRows.length}/${evidenceRows.length || previewRows.length} 条证据`,
    normalizedSaveAction: normalizeAction(data.saveAction, status === 'ready_to_simulate' ? '保存装备' : '暂不可保存'),
    normalizedImportAction: normalizeAction(data.importAction, '导入模板'),
    normalizedResetAction: normalizeAction(data.resetAction, '重置')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: { type: String, value: 'source_reference' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: '装备栏' },
    meta: { type: String, value: '' },
    identityLabel: { type: String, value: '当前构筑' },
    slots: { type: Array, value: [] },
    selectedSlotId: { type: String, value: '' },
    statSummaryRows: { type: Array, value: [] },
    readinessRows: { type: Array, value: [] },
    evidenceRows: { type: Array, value: [] },
    evidencePreviewRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    saveAction: { type: Object, value: {} },
    importAction: { type: Object, value: {} },
    resetAction: { type: Object, value: {} },
    materialSrc: { type: String, value: '' },
    boardMaterialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'state, stateLabel, stateGlyph, slots, selectedSlotId, statSummaryRows, readinessRows, evidenceRows, evidencePreviewRows, evidenceExpanded, saveAction, importAction, resetAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleSlotTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('slottap', {
        slotId: dataset.slotId || '',
        status: dataset.status || ''
      })
    },
    handleConfigTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('configtap', {
        slotId: dataset.slotId || '',
        status: dataset.status || ''
      })
    },
    handleImportTap() {
      this.triggerEvent('importtap', this.data.normalizedImportAction)
    },
    handleResetTap() {
      this.triggerEvent('resettap', this.data.normalizedResetAction)
    },
    handleSaveTap() {
      this.triggerEvent('savetap', this.data.normalizedSaveAction)
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle', { expanded: !this.data.evidenceExpanded })
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
