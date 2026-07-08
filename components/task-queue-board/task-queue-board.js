const STATUS_LABELS = {
  loading: '读取中',
  empty: '暂无任务',
  queued: '排队中',
  running: '模拟中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  blocked: '阻断',
  partial: '部分可用',
  source_reference: '来源参考',
  unknown: '未知'
}

const STATUS_STATES = {
  loading: 'loading',
  empty: 'source_reference',
  queued: 'partial',
  running: 'loading',
  completed: 'verified',
  failed: 'blocked',
  cancelled: 'blocked',
  blocked: 'blocked',
  partial: 'partial',
  source_reference: 'source_reference',
  unknown: 'source_reference'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function normalizeTaskStatus(value) {
  const status = cleanText(value, 'source_reference').toLowerCase()
  return Object.prototype.hasOwnProperty.call(STATUS_LABELS, status) ? status : 'source_reference'
}

function visualState(status) {
  return STATUS_STATES[status] || 'source_reference'
}

function statusLabel(status, fallback) {
  return cleanText(fallback, STATUS_LABELS[status] || STATUS_LABELS.source_reference)
}

function statusGlyph(status, fallback) {
  const explicit = cleanText(fallback)
  if (explicit) return explicit
  if (status === 'completed') return 'OK'
  if (status === 'failed' || status === 'cancelled' || status === 'blocked') return '!'
  if (status === 'running') return '跑'
  if (status === 'queued') return '等'
  if (status === 'loading') return '读'
  if (status === 'empty') return '空'
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

function normalizeRows(rows, fallbackPrefix) {
  return normalizeArray(rows).map((row, index) => {
    const status = cleanText(row.status || row.state, 'source_reference')
    return {
      key: cleanText(row.key || row.id, `${fallbackPrefix}-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value: cleanText(row.value || row.desc, '待读取'),
      status,
      statusLabel: cleanText(row.statusLabel, statusLabel(status))
    }
  })
}

function normalizeTags(tags) {
  return normalizeArray(tags).map((tag, index) => {
    if (typeof tag === 'string') {
      return {
        key: `tag-${index}`,
        label: tag,
        status: 'source_reference'
      }
    }
    return {
      key: cleanText(tag.key || tag.id, `tag-${index}`),
      label: cleanText(tag.label || tag.value, '标签'),
      status: cleanText(tag.status || tag.state, 'source_reference')
    }
  }).slice(0, 4)
}

function normalizeTask(task, index) {
  const status = normalizeTaskStatus(task.status || task.state)
  const id = cleanText(task.id || task.taskId, `task-${index}`)
  const classSpec = [task.className, task.specName].map((item) => cleanText(item)).filter(Boolean).join(' · ')
  const context = cleanText(task.context || task.contextLabel || classSpec || task.profileLabel, '模拟任务')
  const summary = cleanText(task.summary || task.summaryText || task.resultSummary || task.failureSummary, status === 'completed' ? '结果已生成' : '等待任务更新')
  return {
    id,
    status,
    visualState: visualState(status),
    statusLabel: statusLabel(status, task.statusLabel),
    statusGlyph: statusGlyph(status, task.statusGlyph),
    title: cleanText(task.title || task.name, `任务 ${index + 1}`),
    context,
    summary,
    scenario: cleanText(task.scenarioLabel || task.scenario, '场景待确认'),
    createdAt: cleanText(task.createdAt || task.createdLabel),
    updatedAt: cleanText(task.updatedAt || task.updatedLabel || task.finishedAt),
    iconSrc: cleanText(task.iconSrc || task.iconUrl),
    iconName: cleanText(task.iconName),
    fallbackText: cleanText(task.fallbackText || task.specName || task.className || '模').slice(0, 2),
    tags: normalizeTags(task.tags),
    isPreview: Boolean(task.isPreview || task.preview)
  }
}

function buildStatusRail(tasks, activeCounts) {
  const counts = activeCounts || {}
  const computed = {
    queued: tasks.filter((task) => task.status === 'queued').length,
    running: tasks.filter((task) => task.status === 'running').length,
    completed: tasks.filter((task) => task.status === 'completed').length,
    failed: tasks.filter((task) => task.status === 'failed' || task.status === 'cancelled').length
  }
  return [
    { key: 'queued', label: '排队', value: cleanText(counts.queued, String(computed.queued)), status: 'queued' },
    { key: 'running', label: '模拟', value: cleanText(counts.running, String(computed.running)), status: 'running' },
    { key: 'completed', label: '完成', value: cleanText(counts.completed, String(computed.completed)), status: 'completed' },
    { key: 'failed', label: '失败', value: cleanText(counts.failed, String(computed.failed)), status: 'failed' }
  ]
}

function deriveSurfaceStatus(data, tasks) {
  if (data.loading) return 'loading'
  if (data.error) return 'blocked'
  if (data.empty || !tasks.length) return 'empty'
  if (tasks.some((task) => task.status === 'running')) return 'running'
  if (tasks.some((task) => task.status === 'queued')) return 'queued'
  if (tasks.some((task) => task.status === 'failed' || task.status === 'cancelled')) return 'partial'
  return 'completed'
}

function buildState(data) {
  const tasks = normalizeArray(data.tasks).map(normalizeTask)
  const surfaceStatus = deriveSurfaceStatus(data, tasks)
  const evidenceRows = normalizeRows(data.evidenceRows, 'task-evidence')
  const previewRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${visualState(surfaceStatus)} mode-${surfaceStatus}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedSurfaceStatus: surfaceStatus,
    normalizedSurfaceVisualState: visualState(surfaceStatus),
    normalizedSurfaceLabel: statusLabel(surfaceStatus, data.stateLabel),
    normalizedSurfaceGlyph: statusGlyph(surfaceStatus, data.stateGlyph),
    normalizedTasks: tasks,
    normalizedStatusRail: buildStatusRail(tasks, data.activeCounts),
    normalizedEvidenceRows: previewRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${previewRows.length}/${evidenceRows.length} 条证据` : '等待任务证据',
    normalizedGuestLabel: cleanText(data.guestState && data.guestState.label, '游客可查看本机任务'),
    normalizedGuestMeta: cleanText(data.guestState && data.guestState.meta, '登录后可跨设备同步'),
    normalizedErrorText: cleanText(data.errorText || data.error, '任务读取失败，请稍后重试。'),
    normalizedEmptyTitle: cleanText(data.emptyTitle, '暂无模拟任务'),
    normalizedEmptyMeta: cleanText(data.emptyMeta, '从 SimC 或当前专精工作台发起一次可执行模拟后，会在这里复盘。'),
    normalizedSimcAction: normalizeAction(data.simcAction, '去 SimC', 'primary'),
    normalizedWorkbenchAction: normalizeAction(data.workbenchAction, '回工作台', 'secondary'),
    normalizedRetryAction: normalizeAction(data.retryAction, '重试', 'secondary')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: '模拟任务' },
    meta: { type: String, value: '任务历史与结果入口' },
    loading: { type: Boolean, value: false },
    empty: { type: Boolean, value: false },
    error: { type: String, value: '' },
    errorText: { type: String, value: '' },
    tasks: { type: Array, value: [] },
    activeCounts: { type: Object, value: {} },
    guestState: { type: Object, value: {} },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    simcAction: { type: Object, value: {} },
    workbenchAction: { type: Object, value: {} },
    retryAction: { type: Object, value: {} },
    materialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'stateLabel, stateGlyph, loading, empty, error, errorText, tasks, activeCounts, guestState, evidenceRows, evidenceExpanded, simcAction, workbenchAction, retryAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleTaskTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('tasktap', {
        taskId: dataset.taskId || '',
        status: dataset.status || ''
      })
    },
    handleSimcTap() {
      this.triggerEvent('gosimc', this.data.normalizedSimcAction)
    },
    handleWorkbenchTap() {
      this.triggerEvent('goworkbench', this.data.normalizedWorkbenchAction)
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
