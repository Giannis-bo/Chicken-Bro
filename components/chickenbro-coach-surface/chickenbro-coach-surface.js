const SOURCE_LABELS = {
  codex: '通用回答',
  deterministic_fallback: '降级回复',
  deterministic_scope_refusal: '证据不足',
  frontend_fallback: '降级回复',
  local_evidence: '本地证据',
  source_reference: '来源参考'
}

const STRENGTH_LABELS = {
  high: '可解释',
  medium: '部分可用',
  low: '证据不足',
  blocked: '阻断',
  bounded: '部分可用'
}

const JOB_LABELS = {
  queued: '等待整理',
  running: '整理中',
  succeeded: '已完成',
  failed: '暂时失败',
  cancelled: '暂时失败'
}

const MAX_RENDERED_MESSAGES = 40
const MAX_MESSAGE_CONTENT_LENGTH = 3200
const MAX_MESSAGE_EVIDENCE_ROWS = 6
const MAX_NEXT_QUESTIONS = 6

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function cleanLimitedText(value, limit, fallback = '') {
  const text = cleanText(value, fallback)
  if (!text || text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 16))}...（内容已收起）`
}

function mapAnswerSource(value) {
  const key = cleanText(value).toLowerCase()
  return SOURCE_LABELS[key] || (key ? '来源参考' : '证据不足')
}

function mapEvidenceStrength(value) {
  const key = cleanText(value).toLowerCase()
  return STRENGTH_LABELS[key] || (key ? '部分可用' : '证据不足')
}

function mapJobStatus(value) {
  const key = cleanText(value).toLowerCase()
  return JOB_LABELS[key] || (key ? '整理中' : '等待提问')
}

function statusFromData(data) {
  if (data.requestError) return 'error'
  if (data.loading || data.generationStatus === 'generating') return 'loading'
  if (data.generationStatus === 'failed') return 'blocked'
  if (data.generationStatus === 'fallback' || data.fromFallback) return 'partial'
  if (data.generationStatus === 'done') return 'source_reference'
  if (data.contextTitle || data.contextMeta) return 'source_reference'
  return 'empty'
}

function statusLabelFromState(state) {
  if (state === 'loading') return '整理中'
  if (state === 'blocked' || state === 'error') return '暂时失败'
  if (state === 'partial') return '降级回复'
  if (state === 'source_reference') return '可追问'
  return '等待提问'
}

function normalizeMessages(messages) {
  const list = Array.isArray(messages) ? messages : []
  const rendered = list.length > MAX_RENDERED_MESSAGES
    ? list.slice(list.length - MAX_RENDERED_MESSAGES)
    : list
  return rendered.map((item, index) => ({
    id: item.id || item.messageId || `message-${index}`,
    role: item.role === 'user' ? 'user' : 'assistant',
    content: cleanLimitedText(item.content, MAX_MESSAGE_CONTENT_LENGTH, '空消息'),
    status: cleanText(item.status, 'done'),
    evidenceRows: Array.isArray(item.evidenceRows)
      ? item.evidenceRows.slice(0, MAX_MESSAGE_EVIDENCE_ROWS)
      : [],
    nextQuestions: Array.isArray(item.nextQuestions)
      ? item.nextQuestions.slice(0, MAX_NEXT_QUESTIONS).map((question) => cleanLimitedText(question, 80))
      : []
  }))
}

function buildEvidenceRows(data) {
  const payload = data.assistantPayload || {}
  const job = data.job || {}
  const rows = []
  if (payload.answerSource || payload.confidence) {
    rows.push({
      key: 'answer_source',
      iconText: '源',
      label: '回答来源',
      value: mapAnswerSource(payload.answerSource),
      status: payload.answerSource ? 'source_reference' : 'blocked',
      statusLabel: payload.answerSource ? '可解释' : '缺来源'
    })
    rows.push({
      key: 'evidence_strength',
      iconText: '证',
      label: '证据强度',
      value: mapEvidenceStrength(payload.confidence),
      status: payload.confidence === 'blocked' ? 'blocked' : 'partial',
      statusLabel: mapEvidenceStrength(payload.confidence)
    })
  }
  if (job.status || data.generationStatusText) {
    rows.push({
      key: 'job_state',
      iconText: '队',
      label: '队长状态',
      value: mapJobStatus(job.status) || cleanText(data.generationStatusText, '等待提问'),
      status: job.status === 'failed' ? 'blocked' : 'source_reference',
      statusLabel: mapJobStatus(job.status)
    })
  }
  const priorityActions = Array.isArray(payload.priorityActions) ? payload.priorityActions : []
  if (priorityActions.length) {
    rows.push({
      key: 'next_action',
      iconText: '做',
      label: '下一步',
      value: cleanText(priorityActions[0].title, '继续补证据'),
      status: 'partial',
      statusLabel: `${priorityActions.length} 项`
    })
  }
  const limitations = Array.isArray(payload.limitations) ? payload.limitations : []
  if (limitations.length) {
    rows.push({
      key: 'limitations',
      iconText: '限',
      label: '限制说明',
      value: cleanText(limitations[0], '存在未满足证据条件'),
      status: 'source_reference',
      statusLabel: `${limitations.length} 条`
    })
  }
  if (!rows.length && data.requestError) {
    rows.push({
      key: 'request_error',
      iconText: '!',
      label: '请求状态',
      value: cleanText(data.requestError, '暂时失败'),
      status: 'blocked',
      statusLabel: '阻断'
    })
  }
  return rows
}

function buildRootClass(data) {
  const classes = [
    `entry-${cleanText(data.entryMode, 'tab')}`,
    `state-${statusFromData(data)}`
  ]
  if (data.topicDrawerVisible) classes.push('has-drawer')
  if (data.contextTitle || data.contextMeta) classes.push('has-context')
  return classes.join(' ')
}

function buildSurfaceState(data) {
  const statusState = statusFromData(data)
  const contextTitle = cleanText(data.contextTitle || data.contextLabel)
  return {
    rootClass: buildRootClass(data),
    statusState,
    statusLabel: statusLabelFromState(statusState),
    shellMessages: normalizeMessages(data.messages),
    resolvedContextTitle: contextTitle,
    resolvedContextMeta: cleanText(data.contextMeta),
    drawerTitle: cleanText(data.sessionTitle, '当前话题')
  }
}

function stableSignature(value) {
  try {
    return JSON.stringify(value)
  } catch (error) {
    return String(value || '')
  }
}

function assignIfChanged(data, patch, key, value) {
  if (data[key] !== value) patch[key] = value
}

function applySurfaceState(component) {
  const next = buildSurfaceState(component.data)
  const patch = {}
  const shellMessagesSignature = stableSignature(next.shellMessages)

  assignIfChanged(component.data, patch, 'rootClass', next.rootClass)
  assignIfChanged(component.data, patch, 'statusState', next.statusState)
  assignIfChanged(component.data, patch, 'statusLabel', next.statusLabel)
  assignIfChanged(component.data, patch, 'resolvedContextTitle', next.resolvedContextTitle)
  assignIfChanged(component.data, patch, 'resolvedContextMeta', next.resolvedContextMeta)
  assignIfChanged(component.data, patch, 'drawerTitle', next.drawerTitle)

  if (component.data.shellMessagesSignature !== shellMessagesSignature) {
    patch.shellMessages = next.shellMessages
    patch.shellMessagesSignature = shellMessagesSignature
  }
  if (Object.keys(patch).length) component.setData(patch)
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    entryMode: {
      type: String,
      value: 'tab'
    },
    title: {
      type: String,
      value: '炸鸡队长'
    },
    desc: {
      type: String,
      value: '只解释可追踪证据、阻断原因和下一步。'
    },
    materialSrc: {
      type: String,
      value: ''
    },
    contextTitle: {
      type: String,
      value: ''
    },
    contextLabel: {
      type: String,
      value: ''
    },
    contextMeta: {
      type: String,
      value: ''
    },
    suggestedPrompts: {
      type: Array,
      value: []
    },
    messages: {
      type: Array,
      value: []
    },
    assistantPayload: {
      type: Object,
      value: {}
    },
    job: {
      type: Object,
      value: {}
    },
    generationStatus: {
      type: String,
      value: 'idle'
    },
    generationStatusText: {
      type: String,
      value: '等待提问'
    },
    requestError: {
      type: String,
      value: ''
    },
    fromFallback: {
      type: Boolean,
      value: false
    },
    inputValue: {
      type: String,
      value: ''
    },
    inputPlaceholder: {
      type: String,
      value: '问炸鸡队长'
    },
    inputState: {
      type: String,
      value: 'idle'
    },
    inputDisabled: {
      type: Boolean,
      value: false
    },
    loading: {
      type: Boolean,
      value: false
    },
    topicDrawerVisible: {
      type: Boolean,
      value: false
    },
    sessionTitle: {
      type: String,
      value: ''
    },
    safeAreaBottom: {
      type: String,
      value: ''
    },
    scrollIntoView: {
      type: String,
      value: ''
    }
  },
  data: {
    rootClass: '',
    statusState: 'empty',
    statusLabel: '等待提问',
    shellMessages: [],
    shellMessagesSignature: '',
    resolvedContextTitle: '',
    resolvedContextMeta: '',
    drawerTitle: '当前话题'
  },
  observers: {
    'entryMode, contextTitle, contextLabel, contextMeta, messages, assistantPayload, job, generationStatus, generationStatusText, requestError, fromFallback, loading, topicDrawerVisible, sessionTitle': function updateSurface() {
      applySurfaceState(this)
    }
  },
  lifetimes: {
    attached() {
      applySurfaceState(this)
    }
  },
  methods: {
    handleInputChange(event) {
      this.triggerEvent('inputchange', event.detail || {})
    },
    handleInputFocus() {
      this.triggerEvent('inputfocus', {})
    },
    handleInputBlur() {
      this.triggerEvent('inputblur', {})
    },
    handleSend(event) {
      this.triggerEvent('send', event.detail || {})
    },
    handleNewTopic() {
      this.triggerEvent('newtopic', {})
    },
    handleOpenDrawer() {
      this.triggerEvent('opendrawer', {})
    },
    handleCloseDrawer() {
      this.triggerEvent('closedrawer', {})
    },
    handleSuggestedPrompt(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      const index = Number(dataset.index)
      const prompts = Array.isArray(this.data.suggestedPrompts) ? this.data.suggestedPrompts : []
      this.triggerEvent('suggestedprompt', {
        index,
        value: Number.isInteger(index) ? prompts[index] || '' : ''
      })
    },
    handleRetry() {
      this.triggerEvent('retry', {})
    }
  }
})
