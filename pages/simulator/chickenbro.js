const {
  requestChickenbroMessage
} = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

function valueFromDraft(draft, key) {
  const match = String(draft || '').match(new RegExp(`${key}\\s*=\\s*([A-Za-z0-9_-]+)`, 'i'))
  return match ? match[1].toLowerCase() : ''
}

function contextFromDraft(draft) {
  return {
    productPhase: valueFromDraft(draft, 'phase') || 'retail',
    region: valueFromDraft(draft, 'region') || 'cn',
    classKey: valueFromDraft(draft, 'class'),
    specKey: valueFromDraft(draft, 'spec'),
    scenarioKey: valueFromDraft(draft, 'scenario') || 'mplus_fortified'
  }
}

function normalizeChatMessages(payload) {
  const messages = []
  if (payload && payload.userMessage) {
    messages.push({
      messageId: payload.userMessage.messageId || 'local-user-message',
      role: 'user',
      content: payload.userMessage.content || ''
    })
  }
  if (payload && payload.assistantMessage) {
    messages.push({
      messageId: payload.assistantMessage.messageId || 'local-assistant-message',
      role: 'assistant',
      content: payload.assistantMessage.content || '',
      payload: payload.assistantMessage.payload || {}
    })
  }
  return messages
}

function normalizeAssistantPayload(payload) {
  const assistantPayload = (payload && payload.assistantMessage && payload.assistantMessage.payload) || {}
  return {
    answerSource: assistantPayload.answerSource || '',
    confidence: assistantPayload.confidence || '',
    priorityActions: Array.isArray(assistantPayload.priorityActions) ? assistantPayload.priorityActions : [],
    evidenceRefs: Array.isArray(assistantPayload.evidenceRefs) ? assistantPayload.evidenceRefs : [],
    limitations: Array.isArray(assistantPayload.limitations) ? assistantPayload.limitations : []
  }
}

Page({
  data: {
    navTitle: '炸鸡队长',
    kicker: '智能分析 03',
    title: '炸鸡队长',
    desc: '只整理可追踪证据；缺 SimC、WCL、角色上下文或同类样本时，会先列缺失项。',
    loading: false,
    fromFallback: true,
    requestError: '',
    chickenbroPrompt: '角色/专精：\n装等/场景：\n已有 SimC 或 WCL 证据：\n想优先解决的问题：',
    contextDraft: 'class=mage spec=arcane scenario=mplus_fortified',
    session: null,
    job: null,
    chatMessages: [],
    assistantPayload: {
      priorityActions: [],
      evidenceRefs: [],
      limitations: []
    }
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    trackPageView('pages/simulator/chickenbro', { source: 'simulator' })
  },

  onUnload() {
    trackPageLeave('pages/simulator/chickenbro', this.analyticsStartedAt)
  },

  updateChickenbroPrompt(event) {
    this.setData({ chickenbroPrompt: event.detail.value || '' })
  },

  updateContextDraft(event) {
    this.setData({ contextDraft: event.detail.value || '' })
  },

  submitChickenbroMessage() {
    const prompt = (this.data.chickenbroPrompt || '').trim()
    const context = contextFromDraft(this.data.contextDraft)
    this.setData({ loading: true })
    trackEvent('chickenbro_submit', {
      hasPrompt: !!prompt,
      hasSession: !!(this.data.session && this.data.session.sessionId),
      classKey: context.classKey,
      specKey: context.specKey,
      scenarioKey: context.scenarioKey
    }, { page: 'pages/simulator/chickenbro' })
    requestChickenbroMessage({
      message: prompt,
      sessionId: this.data.session && this.data.session.sessionId,
      context
    })
      .then((result = {}) => {
        const { payload, fromFallback, error } = result || {}
        const safePayload = payload || {}
        this.setData({
          session: safePayload.session || null,
          job: safePayload.job || null,
          chatMessages: normalizeChatMessages(safePayload),
          assistantPayload: normalizeAssistantPayload(safePayload),
          fromFallback,
          requestError: error || ''
        })
        wx.showToast({
          title: fromFallback ? '已生成降级回复' : '炸鸡队长已回复',
          icon: 'none'
        })
      }).catch((error) => {
        const message = error && error.message ? error.message : String(error || '炸鸡队长请求失败')
        this.setData({
          requestError: message,
          fromFallback: true
        })
      }).finally(() => {
        this.setData({ loading: false })
      })
  },

  submitChickenbroCoach() {
    this.submitChickenbroMessage()
  }
})
