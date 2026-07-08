const STATUS_LABELS = {
  loading: '读取中',
  missing_id: '缺少任务',
  not_found: '未找到',
  preview: '仅预检',
  final: '已完成',
  failed: '失败',
  blocked: '阻断',
  source_reference: '来源参考'
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
  if (status === 'verified') return status
  if (status === 'blocked') return status
  if (status === 'partial') return status
  if (status === 'stale') return status
  if (status === 'loading') return status
  if (status === 'source_reference') return status
  if (status === 'failed') return 'blocked'
  if (status === 'completed') return 'verified'
  return 'source_reference'
}

function reportMode(data) {
  if (data.loading) return 'loading'
  if (data.missingId) return 'missing_id'
  if (data.notFound) return 'not_found'
  if (data.failed || data.state === 'failed') return 'failed'
  if (data.isFinal) return 'final'
  if (data.isPreview || data.state === 'preview') return 'preview'
  if (data.state === 'blocked') return 'blocked'
  return 'source_reference'
}

function modeVisualState(mode) {
  if (mode === 'loading') return 'loading'
  if (mode === 'final') return 'verified'
  if (mode === 'failed' || mode === 'blocked' || mode === 'missing_id' || mode === 'not_found') return 'blocked'
  if (mode === 'preview') return 'partial'
  return 'source_reference'
}

function modeLabel(mode, fallback) {
  return cleanText(fallback, STATUS_LABELS[mode] || STATUS_LABELS.source_reference)
}

function modeGlyph(mode, fallback) {
  const explicit = cleanText(fallback)
  if (explicit) return explicit
  if (mode === 'final') return 'OK'
  if (mode === 'loading') return '读'
  if (mode === 'preview') return '预'
  if (mode === 'failed' || mode === 'blocked' || mode === 'missing_id' || mode === 'not_found') return '!'
  return '源'
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

function safeDiagnostic(value, fallback) {
  const text = cleanText(value)
  if (!text) return cleanText(fallback, '模拟执行失败，已隐藏底层诊断。')
  if (/sim_signal_handler|segmentation|traceback|stack trace|raw simc|profile|command|stderr|stdout/i.test(text)) {
    return '模拟执行失败，已隐藏底层诊断。'
  }
  return text
}

function normalizeRows(rows, fallbackPrefix, options = {}) {
  return normalizeArray(rows).map((row, index) => {
    const status = normalizeStatus(row.status || row.state)
    const value = options.diagnostic ? safeDiagnostic(row.value || row.desc || row.message) : cleanText(row.value || row.desc || row.message, '待读取')
    return {
      key: cleanText(row.key || row.id, `${fallbackPrefix}-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value,
      status,
      statusLabel: cleanText(row.statusLabel, modeLabel(status))
    }
  })
}

function normalizeTask(task) {
  const data = task || {}
  const title = cleanText(data.title || data.name || data.taskTitle, '模拟任务')
  const classSpec = [data.className, data.specName].map((item) => cleanText(item)).filter(Boolean).join(' · ')
  return {
    id: cleanText(data.id || data.taskId),
    title,
    context: cleanText(data.context || data.contextLabel || classSpec, '任务上下文'),
    scenario: cleanText(data.scenarioLabel || data.scenario, '场景待确认'),
    createdAt: cleanText(data.createdAt || data.createdLabel),
    updatedAt: cleanText(data.updatedAt || data.updatedLabel || data.finishedAt),
    iconSrc: cleanText(data.iconSrc || data.iconUrl),
    iconName: cleanText(data.iconName),
    fallbackText: cleanText(data.fallbackText || data.specName || data.className || title, '模').slice(0, 2)
  }
}

function normalizeMetricRows(data, mode) {
  if (mode !== 'final') {
    return [{
      key: 'gate',
      iconText: '门',
      label: '结果门禁',
      value: mode === 'preview' ? '当前只是预检，不展示最终指标。' : '等待完整任务结果。',
      status: mode === 'preview' ? 'partial' : 'source_reference',
      statusLabel: mode === 'preview' ? '预检' : '等待'
    }]
  }
  const report = data.simcReport || {}
  const metricRows = normalizeArray(data.metricRows).length ? normalizeRows(data.metricRows, 'metric') : normalizeRows(report.metricRows, 'metric')
  if (metricRows.length) return metricRows
  return [{
    key: 'final_state',
    iconText: '结',
    label: '最终结果',
    value: cleanText(report.summary || data.finalSummary, '模拟结果已完成，可继续复盘。'),
    status: 'verified',
    statusLabel: '已验证'
  }]
}

function buildState(data) {
  const mode = reportMode(data)
  const task = normalizeTask(data.task)
  const contextRows = normalizeRows(data.contextRows, 'context')
  const statRows = normalizeRows(data.statRows, 'stat')
  const combatBuffRows = normalizeRows(data.combatBuffRows, 'combat')
  const failureRows = normalizeRows(data.failureRows, 'failure', { diagnostic: true })
  const evidenceRows = normalizeRows(data.evidenceRows, 'result-evidence')
  const visibleEvidenceRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${modeVisualState(mode)} mode-${mode}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedMode: mode,
    normalizedModeVisualState: modeVisualState(mode),
    normalizedModeLabel: modeLabel(mode, data.stateLabel),
    normalizedModeGlyph: modeGlyph(mode, data.stateGlyph),
    normalizedTask: task,
    normalizedMetricRows: normalizeMetricRows(data, mode),
    normalizedContextRows: contextRows,
    normalizedStatRows: statRows,
    normalizedCombatBuffRows: combatBuffRows,
    normalizedFailureRows: mode === 'failed' || mode === 'blocked' ? failureRows : [],
    normalizedEvidenceRows: visibleEvidenceRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${visibleEvidenceRows.length}/${evidenceRows.length} 条证据` : '等待任务证据',
    normalizedBackAction: normalizeAction(data.backAction, '返回列表', 'secondary'),
    normalizedSimcAction: normalizeAction(data.simcAction, '再跑一次', 'primary'),
    normalizedChickenbroAction: normalizeAction(data.chickenbroAction, '问队长', 'secondary'),
    normalizedRetryAction: normalizeAction(data.retryAction, '重试', 'secondary')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: { type: String, value: 'source_reference' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: '任务报告' },
    meta: { type: String, value: '模拟结果与证据' },
    loading: { type: Boolean, value: false },
    missingId: { type: Boolean, value: false },
    notFound: { type: Boolean, value: false },
    failed: { type: Boolean, value: false },
    isPreview: { type: Boolean, value: false },
    isFinal: { type: Boolean, value: false },
    task: { type: Object, value: {} },
    simcReport: { type: Object, value: {} },
    metricRows: { type: Array, value: [] },
    contextRows: { type: Array, value: [] },
    statRows: { type: Array, value: [] },
    combatBuffRows: { type: Array, value: [] },
    failureRows: { type: Array, value: [] },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    backAction: { type: Object, value: {} },
    simcAction: { type: Object, value: {} },
    chickenbroAction: { type: Object, value: {} },
    retryAction: { type: Object, value: {} },
    materialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'state, stateLabel, stateGlyph, loading, missingId, notFound, failed, isPreview, isFinal, task, simcReport, metricRows, contextRows, statRows, combatBuffRows, failureRows, evidenceRows, evidenceExpanded, backAction, simcAction, chickenbroAction, retryAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleBackTap() {
      this.triggerEvent('backtap', this.data.normalizedBackAction)
    },
    handleSimcTap() {
      this.triggerEvent('gosimc', this.data.normalizedSimcAction)
    },
    handleChickenbroTap() {
      this.triggerEvent('askchickenbro', {
        action: this.data.normalizedChickenbroAction,
        taskId: this.data.normalizedTask.id
      })
    },
    handleRetryTap() {
      this.triggerEvent('retrytap', this.data.normalizedRetryAction)
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle', { expanded: !this.data.evidenceExpanded })
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
