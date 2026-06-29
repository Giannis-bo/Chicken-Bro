const { requestChickenbroMessage: defaultRequestChickenbroMessage } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

function cleanText(value, limit = 1000) {
  return String(value || '').trim().slice(0, limit)
}

function valueFromText(text, key) {
  const match = String(text || '').match(new RegExp(`${key}\\s*=\\s*([A-Za-z0-9_-]+)`, 'i'))
  return match ? match[1].toLowerCase() : ''
}

function inferSpecContext(text) {
  const lower = String(text || '').toLowerCase()
  const checks = [
    { terms: ['奥法', 'arcane'], classKey: 'mage', specKey: 'arcane' },
    { terms: ['冰法', 'frost mage'], classKey: 'mage', specKey: 'frost' },
    { terms: ['火法', 'fire mage'], classKey: 'mage', specKey: 'fire' },
    { terms: ['武器战', 'arms warrior'], classKey: 'warrior', specKey: 'arms' },
    { terms: ['狂暴战', 'fury warrior'], classKey: 'warrior', specKey: 'fury' },
    { terms: ['防战', 'protection warrior'], classKey: 'warrior', specKey: 'protection' },
    { terms: ['元素萨', 'elemental shaman'], classKey: 'shaman', specKey: 'elemental' },
    { terms: ['增强萨', 'enhancement shaman'], classKey: 'shaman', specKey: 'enhancement' },
    { terms: ['邪dk', '邪恶dk', 'unholy'], classKey: 'deathknight', specKey: 'unholy' },
    { terms: ['冰dk', 'frost dk'], classKey: 'deathknight', specKey: 'frost' },
    { terms: ['血dk', 'blood dk'], classKey: 'deathknight', specKey: 'blood' },
    { terms: ['浩劫', 'havoc'], classKey: 'demonhunter', specKey: 'havoc' },
    { terms: ['复仇', 'vengeance'], classKey: 'demonhunter', specKey: 'vengeance' },
    { terms: ['噬灭', 'devourer'], classKey: 'demonhunter', specKey: 'devourer' }
  ]
  return checks.find((item) => item.terms.some((term) => lower.includes(term.toLowerCase()))) || {}
}

function inferClassKey(text) {
  const lower = String(text || '').toLowerCase()
  const checks = [
    { terms: ['法师', 'mage'], classKey: 'mage' },
    { terms: ['战士', 'warrior'], classKey: 'warrior' },
    { terms: ['萨满', 'shaman'], classKey: 'shaman' },
    { terms: ['死亡骑士', 'dk', 'deathknight'], classKey: 'deathknight' },
    { terms: ['恶魔猎手', 'dh', 'demonhunter'], classKey: 'demonhunter' },
    { terms: ['术士', 'warlock'], classKey: 'warlock' },
    { terms: ['牧师', 'priest'], classKey: 'priest' },
    { terms: ['盗贼', '潜行者', 'rogue'], classKey: 'rogue' },
    { terms: ['武僧', 'monk'], classKey: 'monk' },
    { terms: ['猎人', 'hunter'], classKey: 'hunter' },
    { terms: ['德鲁伊', 'druid'], classKey: 'druid' },
    { terms: ['圣骑', 'paladin'], classKey: 'paladin' },
    { terms: ['唤魔师', 'evoker'], classKey: 'evoker' }
  ]
  const match = checks.find((item) => item.terms.some((term) => lower.includes(term.toLowerCase())))
  return match ? match.classKey : ''
}

function inferScenarioKey(text) {
  const lower = String(text || '').toLowerCase()
  if (lower.includes('残暴') || lower.includes('tyrannical')) return 'mplus_tyrannical'
  if (lower.includes('强韧') || lower.includes('fortified') || lower.includes('大秘') || lower.includes('m+')) {
    return 'mplus_fortified'
  }
  if (lower.includes('团本') || lower.includes('单体') || lower.includes('raid')) return 'raid_single'
  return 'mplus_fortified'
}

function contextFromMessage(message) {
  const explicitClass = valueFromText(message, 'class')
  const explicitSpec = valueFromText(message, 'spec')
  const explicitScenario = valueFromText(message, 'scenario')
  const inferredSpec = inferSpecContext(message)
  const classKey = explicitClass || inferredSpec.classKey || inferClassKey(message)
  const specKey = explicitSpec || inferredSpec.specKey || ''
  return {
    productPhase: valueFromText(message, 'phase') || 'retail',
    region: valueFromText(message, 'region') || 'cn',
    classKey,
    specKey,
    scenarioKey: explicitScenario || inferScenarioKey(message)
  }
}

function initialMessages() {
  return [
    {
      messageId: 'chickenbro-welcome',
      role: 'assistant',
      content: '我是炸鸡队长。你可以直接说职业、专精、场景和想解决的问题；缺 SimC、WCL 或已发布画像时，我只会说明缺什么和下一步，不会编造 DPS、排名或日志结论。',
      status: 'ready',
      statusText: '证据边界开启'
    }
  ]
}

function emptyAssistantPayload() {
  return {
    answerSource: '',
    confidence: '',
    priorityActions: [],
    evidenceRefs: [],
    limitations: []
  }
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

function normalizeServerMessage(message, fallbackRole) {
  const role = message && message.role ? message.role : fallbackRole
  return {
    messageId: (message && message.messageId) || `server-${role}-${Date.now()}`,
    role,
    content: (message && message.content) || '',
    payload: (message && message.payload) || {},
    status: 'done',
    statusText: role === 'assistant' ? '已完成' : ''
  }
}

function mergeResponseMessages(existingMessages, pendingIds, payload) {
  const blocked = new Set(pendingIds || [])
  const nextMessages = (existingMessages || []).filter((item) => !blocked.has(item.messageId))
  if (payload && payload.userMessage) {
    nextMessages.push(normalizeServerMessage(payload.userMessage, 'user'))
  }
  if (payload && payload.assistantMessage) {
    nextMessages.push(normalizeServerMessage(payload.assistantMessage, 'assistant'))
  }
  return nextMessages
}

function failPendingMessage(existingMessages, pendingAssistantId, errorMessage) {
  return (existingMessages || []).map((item) => {
    if (item.messageId !== pendingAssistantId) return item
    return {
      ...item,
      content: `请求失败：${errorMessage}。没有生成结论。`,
      status: 'failed',
      statusText: '失败'
    }
  })
}

function safeToast(title) {
  if (typeof wx !== 'undefined' && wx && typeof wx.showToast === 'function') {
    wx.showToast({ title, icon: 'none' })
  }
}

function createChickenbroChatPage(options = {}) {
  const requestChickenbroMessage = options.requestChickenbroMessage || defaultRequestChickenbroMessage
  const pagePath = options.pagePath || 'pages/simulator/chickenbro'
  const pageSource = options.source || 'simulator'

  return {
    data: {
      navTitle: options.navTitle || '炸鸡队长',
      showBack: options.showBack !== false,
      kicker: options.kicker || '智能分析',
      title: '炸鸡队长',
      desc: '证据教练只整理可追踪证据；缺资料时先给补证据路径。',
      loading: false,
      fromFallback: false,
      requestError: '',
      chatDraft: '',
      session: null,
      job: null,
      chatMessages: initialMessages(),
      assistantPayload: emptyAssistantPayload(),
      generationStatus: 'idle',
      generationStatusText: '等待提问',
      scrollAnchor: 'chat-bottom',
      topicDrawerVisible: false,
      streamingMode: 'complete_response_fallback'
    },

    onLoad() {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView(pagePath, { source: pageSource })
    },

    onShow() {
      if (this.analyticsVisible === false) {
        this.analyticsStartedAt = Date.now()
        this.analyticsVisible = true
        trackPageView(pagePath, { source: `${pageSource}_resume` })
      }
    },

    onHide() {
      if (this.analyticsVisible !== false) {
        trackPageLeave(pagePath, this.analyticsStartedAt)
        this.analyticsVisible = false
      }
    },

    onUnload() {
      if (this.analyticsVisible !== false) {
        trackPageLeave(pagePath, this.analyticsStartedAt)
        this.analyticsVisible = false
      }
    },

    updateChatDraft(event) {
      this.setData({ chatDraft: (event.detail && event.detail.value) || '' })
    },

    toggleTopicDrawer() {
      this.setData({ topicDrawerVisible: !this.data.topicDrawerVisible })
    },

    closeTopicDrawer() {
      this.setData({ topicDrawerVisible: false })
    },

    startNewTopic() {
      this.setData({
        chatDraft: '',
        session: null,
        job: null,
        chatMessages: initialMessages(),
        assistantPayload: emptyAssistantPayload(),
        requestError: '',
        generationStatus: 'idle',
        generationStatusText: '新话题',
        topicDrawerVisible: false,
        scrollAnchor: 'chat-bottom'
      })
      trackEvent('chickenbro_new_topic', { source: pageSource }, { page: pagePath })
    },

    submitChickenbroMessage() {
      if (this.data.loading) return Promise.resolve()
      const message = cleanText(this.data.chatDraft, 1000)
      if (!message) {
        this.setData({ requestError: '先输入要问炸鸡队长的问题。' })
        safeToast('先输入问题')
        return Promise.resolve()
      }

      const context = contextFromMessage(message)
      const now = Date.now()
      const localUserId = `local-user-${now}`
      const pendingAssistantId = `pending-assistant-${now}`
      const nextMessages = [
        ...(this.data.chatMessages || []),
        {
          messageId: localUserId,
          role: 'user',
          content: message,
          status: 'sending',
          statusText: ''
        },
        {
          messageId: pendingAssistantId,
          role: 'assistant',
          content: '炸鸡队长正在整理证据边界...',
          status: 'pending',
          statusText: '生成中'
        }
      ]

      this.setData({
        chatDraft: '',
        chatMessages: nextMessages,
        loading: true,
        requestError: '',
        generationStatus: 'generating',
        generationStatusText: '生成中',
        scrollAnchor: 'chat-bottom'
      })
      trackEvent('chickenbro_submit', {
        hasSession: !!(this.data.session && this.data.session.sessionId),
        classKey: context.classKey,
        specKey: context.specKey,
        scenarioKey: context.scenarioKey
      }, { page: pagePath })

      // The pending assistant bubble is the future onChunkReceived update target.
      return requestChickenbroMessage({
        message,
        sessionId: this.data.session && this.data.session.sessionId,
        context
      }).then((result = {}) => {
        const { payload, fromFallback, error } = result || {}
        const safePayload = payload || {}
        this.setData({
          session: safePayload.session || this.data.session,
          job: safePayload.job || null,
          chatMessages: mergeResponseMessages(this.data.chatMessages, [localUserId, pendingAssistantId], safePayload),
          assistantPayload: normalizeAssistantPayload(safePayload),
          fromFallback: !!fromFallback,
          requestError: error || '',
          generationStatus: fromFallback ? 'fallback' : 'done',
          generationStatusText: fromFallback ? '降级完成' : '已完成',
          scrollAnchor: 'chat-bottom'
        })
        safeToast(fromFallback ? '已生成降级回复' : '炸鸡队长已回复')
      }).catch((error) => {
        const messageText = error && error.message ? error.message : String(error || '炸鸡队长请求失败')
        this.setData({
          job: null,
          chatMessages: failPendingMessage(this.data.chatMessages, pendingAssistantId, messageText),
          assistantPayload: emptyAssistantPayload(),
          requestError: messageText,
          fromFallback: true,
          generationStatus: 'failed',
          generationStatusText: '失败',
          scrollAnchor: 'chat-bottom'
        })
      }).finally(() => {
        this.setData({ loading: false })
      })
    },

    submitChickenbroCoach() {
      return this.submitChickenbroMessage()
    }
  }
}

module.exports = {
  contextFromMessage,
  createChickenbroChatPage,
  emptyAssistantPayload,
  initialMessages,
  mergeResponseMessages,
  normalizeAssistantPayload
}
