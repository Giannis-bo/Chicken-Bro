const TYPE_LABELS = {
  talent: '天赋模板',
  gear: '装备模板'
}

const REMOTE_LABELS = {
  local_only: '本地',
  syncing: '同步中',
  synced: '已同步',
  remote_failed: '同步受限',
  unknown: '来源参考'
}

const REMOTE_STATES = {
  local_only: 'source_reference',
  syncing: 'loading',
  synced: 'verified',
  remote_failed: 'partial',
  unknown: 'source_reference'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function normalizeRemoteState(value) {
  const state = cleanText(value, 'local_only').toLowerCase()
  return Object.prototype.hasOwnProperty.call(REMOTE_LABELS, state) ? state : 'unknown'
}

function normalizeRows(rows) {
  return normalizeArray(rows).map((row, index) => ({
    key: cleanText(row.key || row.id, `template-evidence-${index}`),
    iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
    label: cleanText(row.label, '证据'),
    value: cleanText(row.value || row.desc, '待读取'),
    status: cleanText(row.status || row.state, 'source_reference'),
    statusLabel: cleanText(row.statusLabel, '来源参考')
  }))
}

function normalizeAction(action, fallbackLabel, fallbackTone) {
  const data = action || {}
  return {
    key: cleanText(data.key || data.actionKey),
    label: cleanText(data.label, fallbackLabel),
    tone: cleanText(data.tone, fallbackTone || 'secondary'),
    disabled: Boolean(data.disabled),
    loading: Boolean(data.loading)
  }
}

function templateMetaChips(template) {
  const fields = [
    template.className || template.classKey,
    template.specName || template.specKey,
    template.heroLabel || template.heroKey,
    template.scenarioTitle
  ]
  const chips = []
  fields.forEach((value) => {
    const text = cleanText(value)
    if (text && !chips.includes(text)) chips.push(text)
  })
  return chips.slice(0, 4)
}

function normalizeTemplate(template, type, index) {
  const data = template || {}
  const finalType = cleanText(data.type, type)
  const remoteState = normalizeRemoteState(data.remoteState || (data.remote ? 'synced' : 'local_only'))
  const title = cleanText(data.title, finalType === 'gear' ? '未命名装备模板' : '未命名天赋模板')
  return {
    id: cleanText(data.id || data.templateId, `${finalType}-${index}`),
    type: finalType,
    typeLabel: TYPE_LABELS[finalType] || '模板',
    title,
    status: REMOTE_STATES[remoteState],
    statusLabel: cleanText(data.statusLabel, REMOTE_LABELS[remoteState]),
    statusGlyph: remoteState === 'synced' ? 'OK' : remoteState === 'remote_failed' ? '!' : '本',
    iconSrc: cleanText(data.iconSrc || data.iconUrl),
    fallbackText: cleanText(data.fallbackText || title.slice(0, 1), finalType === 'gear' ? '装' : '天').slice(0, 2),
    metaChips: normalizeArray(data.metaChips).length ? normalizeArray(data.metaChips).slice(0, 4) : templateMetaChips(data),
    savedTimeLabel: cleanText(data.savedTimeLabel || data.savedLabel || data.updatedAt || data.createdAt, '本地保存'),
    sourceLabel: cleanText(data.sourceLabel || data.source, remoteState === 'synced' ? '远端合并' : '本地模板'),
    entryAction: normalizeAction(data.entryAction, finalType === 'gear' ? '查看装备' : '查看天赋', 'secondary'),
    deleteAction: normalizeAction(data.deleteAction, '删除', 'danger')
  }
}

function normalizeModule(type, templates, emptyText) {
  const list = normalizeArray(templates).map((template, index) => normalizeTemplate(template, type, index))
  const readyCount = list.filter((item) => item.status === 'verified').length
  return {
    type,
    title: TYPE_LABELS[type] || '模板',
    count: list.length,
    metric: `${list.length}`,
    meta: list.length ? `最近 ${Math.min(list.length, 3)} 个 · 已同步 ${readyCount}` : cleanText(emptyText, '暂无模板'),
    status: list.length ? (readyCount === list.length ? 'verified' : 'source_reference') : 'source_reference',
    statusLabel: list.length ? '有记录' : '空',
    statusGlyph: type === 'gear' ? '装' : '天',
    iconText: type === 'gear' ? '装' : '天',
    emptyText: cleanText(emptyText, type === 'gear' ? '装备模板会在保存装备配置后出现。' : '天赋模板会在保存天赋方案后出现。'),
    recent: list.slice(0, 6)
  }
}

function buildState(data) {
  const remoteState = normalizeRemoteState(data.remoteState)
  const modules = [
    normalizeModule('talent', data.talentTemplates, data.emptyTalentText),
    normalizeModule('gear', data.gearTemplates, data.emptyGearText)
  ]
  const allTemplates = modules.reduce((items, module) => items.concat(module.recent), [])
  const evidenceRows = normalizeRows(data.evidenceRows)
  const visibleEvidenceRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  const deleteState = data.deleteState || {}
  return {
    rootClass: `state-${REMOTE_STATES[remoteState]} remote-${remoteState}${deleteState.confirming ? ' is-delete-confirming' : ''}`,
    normalizedRemoteState: remoteState,
    normalizedRemoteVisual: REMOTE_STATES[remoteState],
    normalizedRemoteLabel: cleanText(data.remoteLabel, REMOTE_LABELS[remoteState]),
    normalizedRemoteGlyph: remoteState === 'synced' ? 'OK' : remoteState === 'remote_failed' ? '!' : remoteState === 'syncing' ? '读' : '本',
    normalizedModules: modules,
    normalizedAllTemplates: allTemplates,
    normalizedIsEmpty: !allTemplates.length,
    normalizedLoading: Boolean(data.loading),
    normalizedEmptyTitle: cleanText(data.emptyTitle, '还没有保存模板'),
    normalizedEmptyMeta: cleanText(data.emptyMeta, '从天赋模拟器或装备页保存后，会按类型进入这里。'),
    normalizedSyncAction: normalizeAction(data.syncAction, remoteState === 'remote_failed' ? '重试同步' : '刷新模板', 'secondary'),
    normalizedTalentAction: normalizeAction(data.talentAction, '去天赋页', 'primary'),
    normalizedGearAction: normalizeAction(data.gearAction, '去装备页', 'secondary'),
    normalizedDeleteState: {
      confirming: Boolean(deleteState.confirming),
      templateId: cleanText(deleteState.templateId),
      title: cleanText(deleteState.title, '这个模板'),
      message: cleanText(deleteState.message, '删除后本机模板会立即移除；远端失败时会显示同步受限。'),
      confirmAction: normalizeAction(deleteState.confirmAction, '确认删除', 'danger'),
      cancelAction: normalizeAction(deleteState.cancelAction, '取消', 'secondary')
    },
    normalizedEvidenceRows: visibleEvidenceRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${visibleEvidenceRows.length}/${evidenceRows.length} 条证据` : '模板同步证据'
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    title: { type: String, value: '个人模板库' },
    meta: { type: String, value: '天赋与装备模板' },
    loading: { type: Boolean, value: false },
    remoteState: { type: String, value: 'local_only' },
    remoteLabel: { type: String, value: '' },
    talentTemplates: { type: Array, value: [] },
    gearTemplates: { type: Array, value: [] },
    deleteState: { type: Object, value: {} },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    syncAction: { type: Object, value: {} },
    talentAction: { type: Object, value: {} },
    gearAction: { type: Object, value: {} },
    emptyTitle: { type: String, value: '' },
    emptyMeta: { type: String, value: '' },
    emptyTalentText: { type: String, value: '' },
    emptyGearText: { type: String, value: '' },
    materialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'loading, remoteState, remoteLabel, talentTemplates, gearTemplates, deleteState, evidenceRows, evidenceExpanded, syncAction, talentAction, gearAction, emptyTitle, emptyMeta, emptyTalentText, emptyGearText': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleModuleTap(event) {
      const type = event.currentTarget.dataset.type || ''
      this.triggerEvent(type === 'gear' ? 'opengeartemplate' : 'opentalenttemplate', { type })
    },
    handleTemplateTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent(dataset.type === 'gear' ? 'opengeartemplate' : 'opentalenttemplate', {
        templateId: dataset.templateId || '',
        type: dataset.type || ''
      })
    },
    handleConfirmDelete(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('confirmdelete', {
        templateId: dataset.templateId || '',
        title: dataset.title || ''
      })
    },
    handleCancelDelete() {
      this.triggerEvent('canceldelete')
    },
    handleDeleteTemplate() {
      this.triggerEvent('deletetemplate', {
        templateId: this.data.normalizedDeleteState.templateId
      })
    },
    handleSyncTap() {
      this.triggerEvent('retrysync')
    },
    handleTalentEntry() {
      this.triggerEvent('opentalenttemplate', { type: 'talent' })
    },
    handleGearEntry() {
      this.triggerEvent('opengeartemplate', { type: 'gear' })
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle', {
        expanded: !this.data.evidenceExpanded
      })
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
