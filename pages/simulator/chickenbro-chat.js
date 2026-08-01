const { requestChickenbroMessage: defaultRequestChickenbroMessage } = require('./simulator-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { syncTabBarSelected } = require('../common/tabbar-sync')

const MAX_CHAT_MESSAGES = 40
const MAX_MESSAGE_CONTENT_LENGTH = 4000
const MAX_PAYLOAD_ITEMS = 6
const CHAT_BOTTOM_ANCHORS = ['chat-bottom-a', 'chat-bottom-b']

function cleanText(value, limit = 1000) {
  return String(value || '').trim().slice(0, limit)
}

function valueFromText(text, key) {
  const match = String(text || '').match(new RegExp(`${key}\\s*=\\s*([A-Za-z0-9_-]+)`, 'i'))
  return match ? match[1].toLowerCase() : ''
}

function decodeQueryText(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  try {
    return decodeURIComponent(text)
  } catch (error) {
    return text
  }
}

function scenarioLabel(key) {
  const labels = {
    single: '单体',
    raid_single: '单体',
    aoe_5: '5目标',
    mythic_plus: '大秘境',
    mplus_fortified: '大秘境',
    mplus_tyrannical: '大秘境'
  }
  return labels[String(key || '').trim()] || String(key || '').trim() || '当前场景'
}

function backendScenarioKey(key) {
  const value = String(key || '').trim()
  if (value === 'single') return 'raid_single'
  if (value === 'aoe_5' || value === 'mythic_plus') return 'mplus_fortified'
  return value
}

function hasScenarioSignal(text) {
  const lower = String(text || '').toLowerCase()
  return !!valueFromText(text, 'scenario') ||
    /单体|团本|raid|大秘|m\+|强韧|fortified|残暴|tyrannical|aoe|目标/.test(lower)
}

function boundedContextFromOptions(options = {}) {
  const from = decodeQueryText(options.from)
  const classKey = decodeQueryText(options.classKey)
  const specKey = decodeQueryText(options.specKey)
  const scenarioKey = backendScenarioKey(decodeQueryText(options.scenario))
  const specLabel = decodeQueryText(options.spec).replace(/[-_/]+/g, ' · ')
  if (from !== 'workbench' && !classKey && !specKey && !specLabel) return null
  const label = [
    specLabel || [classKey, specKey].filter(Boolean).join(' / '),
    scenarioLabel(decodeQueryText(options.scenario) || scenarioKey)
  ].filter(Boolean).join(' · ')
  return {
    productPhase: 'retail',
    region: 'cn',
    source: from || 'route',
    classKey,
    specKey,
    scenarioKey,
    contextLabel: label,
    specLabel
  }
}

function suggestedPromptsForContext(context) {
  if (!context || !context.contextLabel) return []
  return [
    '现在主要阻断是什么？',
    '我应该先补天赋还是装备？',
    '这些证据能不能提交 SimC？'
  ]
}

function defaultSuggestedPrompts() {
  return [
    '冰法现在能不能模拟？',
    '缺装备时先补什么？',
    '帮我解释 SimC 阻断',
    '大秘境场景怎么补证据？'
  ]
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

function initialMessages(context = null) {
  if (context && context.contextLabel) {
    return [
      {
        messageId: 'chickenbro-welcome',
        role: 'assistant',
        content: `我已带入 ${context.contextLabel} 的工作台上下文。你可以追问阻断、来源或下一步；我只解释证据边界，不会编造 DPS、排名或日志结论。`,
        status: 'ready',
        statusText: '工作台上下文已带入'
      }
    ]
  }
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

const ANSWER_LAYER_LABELS = {
  direct_chat: '直聊',
  diagnostic: '诊断',
  evidence: '证据'
}

function mergeMessageContext(baseContext, inferredContext, message) {
  const base = baseContext || {}
  const inferred = inferredContext || {}
  return {
    productPhase: inferred.productPhase || base.productPhase || 'retail',
    region: inferred.region || base.region || 'cn',
    classKey: inferred.classKey || base.classKey || '',
    specKey: inferred.specKey || base.specKey || '',
    scenarioKey: hasScenarioSignal(message)
      ? backendScenarioKey(inferred.scenarioKey)
      : (base.scenarioKey || backendScenarioKey(inferred.scenarioKey))
  }
}

function emptyAssistantPayload() {
  return {
    answerSource: '',
    confidence: '',
    answerLayer: '',
    answerLayerLabel: '',
    basisLabel: '',
    priorityActions: [],
    evidenceRefs: [],
    limitations: [],
    missingInputs: [],
    nextQuestion: ''
  }
}

function compactAction(action) {
  const item = action || {}
  return {
    title: cleanText(item.title, 160),
    evidenceRefs: Array.isArray(item.evidenceRefs)
      ? item.evidenceRefs.slice(0, MAX_PAYLOAD_ITEMS).map((ref) => cleanText(ref, 120)).filter(Boolean)
      : []
  }
}

function normalizeAssistantPayload(payload) {
  const assistantPayload = (payload && payload.assistantMessage && payload.assistantMessage.payload) || {}
  const answerLayer = assistantPayload.answerLayer || ''
  return {
    answerSource: cleanText(assistantPayload.answerSource, 80),
    confidence: cleanText(assistantPayload.confidence, 80),
    answerLayer,
    answerLayerLabel: ANSWER_LAYER_LABELS[answerLayer] || '',
    basisLabel: cleanText(assistantPayload.basisLabel, 160),
    priorityActions: Array.isArray(assistantPayload.priorityActions)
      ? assistantPayload.priorityActions.slice(0, MAX_PAYLOAD_ITEMS).map(compactAction)
      : [],
    evidenceRefs: Array.isArray(assistantPayload.evidenceRefs)
      ? assistantPayload.evidenceRefs.slice(0, MAX_PAYLOAD_ITEMS).map((ref) => cleanText(ref, 120)).filter(Boolean)
      : [],
    limitations: Array.isArray(assistantPayload.limitations)
      ? assistantPayload.limitations.slice(0, MAX_PAYLOAD_ITEMS).map((item) => cleanText(item, 200)).filter(Boolean)
      : [],
    missingInputs: Array.isArray(assistantPayload.missingInputs)
      ? assistantPayload.missingInputs.slice(0, MAX_PAYLOAD_ITEMS).map((item) => cleanText(item, 120)).filter(Boolean)
      : [],
    nextQuestion: cleanText(assistantPayload.nextQuestion, 200)
  }
}

function compactSession(session, fallback = null) {
  const source = session || fallback || null
  if (!source) return null
  return {
    sessionId: cleanText(source.sessionId, 120),
    title: cleanText(source.title, 160)
  }
}

function compactJob(job) {
  if (!job) return null
  return {
    jobId: cleanText(job.jobId, 120),
    status: cleanText(job.status, 40)
  }
}

function normalizeServerMessage(message, fallbackRole) {
  const role = message && message.role ? message.role : fallbackRole
  return {
    messageId: cleanText((message && message.messageId) || `server-${role}-${Date.now()}`, 120),
    role,
    content: cleanText(message && message.content, MAX_MESSAGE_CONTENT_LENGTH),
    status: cleanText(message && message.status, 40) || 'done',
    statusText: role === 'assistant' ? '已完成' : cleanText(message && message.statusText, 80)
  }
}

function normalizeChatStateMessage(message, index) {
  const item = message || {}
  const role = item.role === 'user' ? 'user' : 'assistant'
  return {
    messageId: cleanText(item.messageId || item.id || `message-${index}`, 120),
    role,
    content: cleanText(item.content, MAX_MESSAGE_CONTENT_LENGTH),
    status: cleanText(item.status, 40) || 'done',
    statusText: cleanText(item.statusText, 80)
  }
}

function compactChatMessages(messages) {
  const list = (Array.isArray(messages) ? messages : []).map(normalizeChatStateMessage)
  if (list.length <= MAX_CHAT_MESSAGES) return list
  const welcome = list.find((item) => item.messageId === 'chickenbro-welcome')
  const tail = list.slice(list.length - MAX_CHAT_MESSAGES)
  if (!welcome || tail.some((item) => item.messageId === welcome.messageId)) return tail
  return [welcome, ...tail.slice(1)]
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
  return compactChatMessages(nextMessages)
}

function failPendingMessage(existingMessages, pendingAssistantId, errorMessage) {
  return compactChatMessages((existingMessages || []).map((item) => {
    if (item.messageId !== pendingAssistantId) return item
    return {
      ...item,
      content: `请求失败：${errorMessage}。没有生成结论。`,
      status: 'failed',
      statusText: '失败'
    }
  }))
}

function nextChatBottomAnchor(current) {
  return current === CHAT_BOTTOM_ANCHORS[0] ? CHAT_BOTTOM_ANCHORS[1] : CHAT_BOTTOM_ANCHORS[0]
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
  const tabIndex = Number.isInteger(options.tabIndex) ? options.tabIndex : -1

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
      lastSubmittedMessage: '',
      lastSubmittedClientMessageId: '',
      session: null,
      job: null,
      chatMessages: initialMessages(),
      assistantPayload: emptyAssistantPayload(),
      boundedContext: null,
      entryMode: 'tab',
      contextLabel: '',
      contextMeta: '',
      suggestedPrompts: defaultSuggestedPrompts(),
      generationStatus: 'idle',
      generationStatusText: '等待提问',
      scrollAnchor: CHAT_BOTTOM_ANCHORS[0],
      topicDrawerVisible: false,
      inputState: 'idle',
      isTabEntry: !!options.tabEntry,
      chatSafeAreaBottom: options.chatSafeAreaBottom || (options.tabEntry ? '0rpx' : ''),
      evidenceExpanded: false,
      streamingMode: 'complete_response_fallback'
    },

    onLoad(options = {}) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      if (tabIndex >= 0) syncTabBarSelected(this, tabIndex)
      const boundedContext = boundedContextFromOptions(options)
      if (boundedContext) {
        this.setData({
          title: '炸鸡队长',
          desc: '已接入工作台上下文，只解释证据、阻断和下一步。',
          boundedContext,
          entryMode: 'workbench_context',
          contextLabel: boundedContext.contextLabel,
          contextMeta: '来自当前专精工作台',
          suggestedPrompts: suggestedPromptsForContext(boundedContext),
          chatMessages: compactChatMessages(initialMessages(boundedContext)),
          generationStatusText: '已带入工作台'
        })
      }
      trackPageView(pagePath, { source: pageSource })
    },

    onShow() {
      if (tabIndex >= 0) syncTabBarSelected(this, tabIndex)
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

    handleInputFocus() {
      this.setData({ inputState: 'focused' })
    },

    handleInputBlur() {
      this.setData({ inputState: 'idle' })
    },

    toggleTopicDrawer() {
      this.setData({ topicDrawerVisible: !this.data.topicDrawerVisible })
    },

    closeTopicDrawer() {
      this.setData({ topicDrawerVisible: false })
    },

    startNewTopic() {
      this.activeChickenbroRequestId = ''
      this.setData({
        chatDraft: '',
        lastSubmittedMessage: '',
        lastSubmittedClientMessageId: '',
        session: null,
        job: null,
        chatMessages: compactChatMessages(initialMessages()),
        assistantPayload: emptyAssistantPayload(),
        boundedContext: null,
        entryMode: 'tab',
        contextLabel: '',
        contextMeta: '',
        suggestedPrompts: defaultSuggestedPrompts(),
        loading: false,
        requestError: '',
        generationStatus: 'idle',
        generationStatusText: '新话题',
        topicDrawerVisible: false,
        inputState: 'idle',
        evidenceExpanded: false,
        scrollAnchor: nextChatBottomAnchor(this.data.scrollAnchor)
      })
      trackEvent('chickenbro_new_topic', { source: pageSource }, { page: pagePath })
    },

    useSuggestedPrompt(event) {
      const detail = (event && event.detail) || {}
      if (detail.value) {
        this.setData({ chatDraft: detail.value })
        return
      }
      const index = Number((((event || {}).currentTarget || {}).dataset || {}).index)
      const prompts = this.data.suggestedPrompts || []
      if (!Number.isInteger(index) || index < 0 || index >= prompts.length) return
      this.setData({ chatDraft: prompts[index] })
    },

    toggleEvidenceExpanded(event) {
      const expanded = !!(event && event.detail && event.detail.expanded)
      this.setData({ evidenceExpanded: expanded })
    },

    retryChickenbroMessage() {
      const message = cleanText(this.data.chatDraft || this.data.lastSubmittedMessage, 1000)
      if (!message) {
        this.setData({ requestError: '先输入要问炸鸡队长的问题。' })
        safeToast('先输入问题')
        return Promise.resolve()
      }
      this.setData({ chatDraft: message })
      return this.submitChickenbroMessage({ retry: true })
    },

    submitChickenbroMessage(options = {}) {
      if (this.data.loading) return Promise.resolve()
      const message = cleanText(this.data.chatDraft, 1000)
      if (!message) {
        this.setData({ requestError: '先输入要问炸鸡队长的问题。' })
        safeToast('先输入问题')
        return Promise.resolve()
      }

      const context = mergeMessageContext(this.data.boundedContext, contextFromMessage(message), message)
      const now = Date.now()
      this.chickenbroMessageSequence = (this.chickenbroMessageSequence || 0) + 1
      const priorClientMessageId = cleanText(this.data.lastSubmittedClientMessageId, 96)
      const clientMessageId = options.retry && /^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$/.test(priorClientMessageId)
        ? priorClientMessageId
        : `turn-${now}-${this.chickenbroMessageSequence}`
      const localUserId = clientMessageId
      const pendingAssistantId = `pending-assistant-${clientMessageId}-${now}`
      const userAlreadyDisplayed = (this.data.chatMessages || []).some((item) => item.messageId === localUserId && item.role === 'user')
      const nextMessages = compactChatMessages([
        ...(this.data.chatMessages || []),
        ...(userAlreadyDisplayed ? [] : [{
          messageId: localUserId,
          role: 'user',
          content: message,
          status: 'sending',
          statusText: ''
        }]),
        {
          messageId: pendingAssistantId,
          role: 'assistant',
          content: '炸鸡队长正在整理证据边界...',
          status: 'pending',
          statusText: '生成中'
        }
      ])
      const requestId = pendingAssistantId
      this.activeChickenbroRequestId = requestId

      this.setData({
        chatDraft: '',
        lastSubmittedMessage: message,
        lastSubmittedClientMessageId: clientMessageId,
        chatMessages: nextMessages,
        loading: true,
        requestError: '',
        generationStatus: 'generating',
        generationStatusText: '生成中',
        inputState: 'idle',
        evidenceExpanded: false,
        scrollAnchor: nextChatBottomAnchor(this.data.scrollAnchor)
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
        context,
        clientMessageId
      }).then((result = {}) => {
        if (this.activeChickenbroRequestId !== requestId) return
        const { payload, fromFallback, error } = result || {}
        const safePayload = payload || {}
        this.setData({
          session: compactSession(safePayload.session, this.data.session),
          job: compactJob(safePayload.job),
          chatMessages: mergeResponseMessages(this.data.chatMessages, [localUserId, pendingAssistantId], safePayload),
          assistantPayload: normalizeAssistantPayload(safePayload),
          fromFallback: !!fromFallback,
          requestError: error || '',
          generationStatus: fromFallback ? 'fallback' : 'done',
          generationStatusText: fromFallback ? '降级完成' : '已完成',
          loading: false,
          scrollAnchor: nextChatBottomAnchor(this.data.scrollAnchor)
        })
        this.activeChickenbroRequestId = ''
        safeToast(fromFallback ? '已生成降级回复' : '炸鸡队长已回复')
      }).catch((error) => {
        if (this.activeChickenbroRequestId !== requestId) return
        const messageText = error && error.message ? error.message : String(error || '炸鸡队长请求失败')
        this.setData({
          job: null,
          chatMessages: failPendingMessage(this.data.chatMessages, pendingAssistantId, messageText),
          assistantPayload: emptyAssistantPayload(),
          requestError: messageText,
          fromFallback: true,
          generationStatus: 'failed',
          generationStatusText: '失败',
          loading: false,
          scrollAnchor: nextChatBottomAnchor(this.data.scrollAnchor)
        })
        this.activeChickenbroRequestId = ''
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
