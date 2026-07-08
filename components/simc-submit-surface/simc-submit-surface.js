const STATE_LABELS = {
  ready_to_simulate: '可提交',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  loading: '检查中',
  unknown: '未知'
}

const STATE_GLYPHS = {
  ready_to_simulate: 'Sim',
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

function normalizeState(value) {
  const state = cleanText(value, 'source_reference')
  return Object.prototype.hasOwnProperty.call(STATE_LABELS, state) ? state : 'source_reference'
}

function stateLabel(state, fallback) {
  return cleanText(fallback, STATE_LABELS[state] || STATE_LABELS.source_reference)
}

function stateGlyph(state, fallback) {
  return cleanText(fallback, STATE_GLYPHS[state] || STATE_GLYPHS.source_reference)
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

function normalizeModule(module, index) {
  const status = normalizeState(module.status || module.state)
  return {
    key: cleanText(module.key || module.id, `simc-module-${index}`),
    title: cleanText(module.title, '检查项'),
    metric: cleanText(module.metric, '待读取'),
    meta: cleanText(module.meta || module.desc || module.statusLabel),
    status,
    statusLabel: stateLabel(status, module.statusLabel),
    statusGlyph: stateGlyph(status, module.statusGlyph),
    iconSrc: cleanText(module.iconSrc || module.iconUrl),
    iconText: cleanText(module.iconText || module.title, '检').slice(0, 2),
    disabled: Boolean(module.disabled)
  }
}

function normalizeEvidenceRows(rows) {
  return normalizeArray(rows).map((row, index) => {
    const status = normalizeState(row.status || row.state)
    return {
      key: cleanText(row.key || row.id, `simc-evidence-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value: cleanText(row.value || row.desc, '待读取'),
      status,
      statusLabel: stateLabel(status, row.statusLabel)
    }
  })
}

function buildState(data) {
  const state = normalizeState(data.state)
  const modules = normalizeArray(data.modules).map(normalizeModule)
  const evidenceRows = normalizeEvidenceRows(data.evidenceRows)
  const previewRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${state}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedState: state,
    normalizedStateLabel: stateLabel(state, data.stateLabel),
    normalizedStateGlyph: stateGlyph(state, data.stateGlyph),
    normalizedTitle: cleanText(data.title, 'SimC 校验'),
    normalizedMeta: cleanText(data.meta, '只提交证据完整的 profile'),
    normalizedSummary: cleanText(data.summary, '确认天赋、装备、场景和模板证据后再提交。'),
    normalizedReadinessMeta: modules.length ? `${modules.length} 项检查` : '等待检查项',
    normalizedModules: modules,
    normalizedActionMeta: cleanText(data.actionMeta, state === 'ready_to_simulate' ? '可进入提交' : '先补齐阻断项'),
    normalizedPrimaryAction: normalizeAction(data.primaryAction, state === 'ready_to_simulate' ? '提交 SimC' : '补齐输入', state === 'blocked' ? 'danger' : 'primary'),
    normalizedSecondaryAction: normalizeAction(data.secondaryAction, '回工作台', 'secondary'),
    normalizedEvidenceRows: previewRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${previewRows.length}/${evidenceRows.length} 条证据` : '等待 SimC 证据'
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: { type: String, value: 'source_reference' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: 'SimC 校验' },
    meta: { type: String, value: '' },
    summary: { type: String, value: '' },
    profileId: { type: String, value: '' },
    profileLabel: { type: String, value: '当前 profile' },
    profileIconUrl: { type: String, value: '' },
    profileFallbackText: { type: String, value: 'Sim' },
    modules: { type: Array, value: [] },
    primaryAction: { type: Object, value: {} },
    secondaryAction: { type: Object, value: {} },
    actionMeta: { type: String, value: '' },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    heroMaterialSrc: { type: String, value: '' },
    readinessMaterialSrc: { type: String, value: '' },
    actionMaterialSrc: { type: String, value: '' },
    evidenceMaterialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    '**': function observeAll(data) {
      this.setData(buildState(data))
    }
  },
  methods: {
    handleModuleTap(event) {
      this.triggerEvent('moduletap', event.detail || {})
    },
    handlePrimaryAction() {
      this.triggerEvent('primaryaction')
    },
    handleSecondaryAction() {
      this.triggerEvent('secondaryaction')
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle')
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
