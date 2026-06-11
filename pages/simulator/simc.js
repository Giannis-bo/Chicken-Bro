const { loginWithWechat } = require('../common/auth-client')
const {
  requestSimulatorAnalysis
} = require('./simulator-api')

const SIMC_BUILD_CONTEXT_STORAGE_KEY = 'wow_simc_build_context'

Page({
  data: {
    navTitle: '模拟 SimC',
    kicker: '智能分析 01',
    title: '模拟 SimC',
    desc: '用聊天方式确认角色、场景和模拟目标，信息足够后再提交 SimC 任务。',
    messages: [
      {
        id: 'msg-0',
        role: 'ai',
        text: '告诉我你的职业专精、装等和想看的场景，例如“我是290元素萨，想看大秘境 AOE DPS 是否合格”。'
      }
    ],
    messageSeq: 1,
    chatInput: '',
    chatAnchor: 'chat-bottom',
    conversationRound: 0,
    loadingChat: false,
    submittingTask: false,
    canSubmitTask: false,
    taskSubmitted: false,
    submittedTaskId: '',
    confirmedPrompt: '',
    pendingBuildContext: null,
    buildContextTitle: '',
    fromFallback: true,
    requestError: '',
    latestAnalysis: null
  },

  onLoad(options) {
    this.loadBuildContext(options || {})
  },

  loadBuildContext(options) {
    if (!options || options.from !== 'builds') return
    if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return
    const context = wx.getStorageSync(SIMC_BUILD_CONTEXT_STORAGE_KEY)
    if (!context || !context.specId) return
    const prompt = this.buildPromptFromContext(context)
    this.setData({
      pendingBuildContext: context,
      buildContextTitle: `${context.specName || ''}${context.className || ''} · ${context.activeQueryTitle || '构筑方案'}`,
      messages: [
        {
          id: 'msg-0',
          role: 'ai',
          text: '已带入职业专精页的天赋、装备、属性和来源上下文。我会先确认能否生成 SimC 模板，再让你提交任务。'
        }
      ],
      messageSeq: 1
    }, () => {
      this.sendChatContent(prompt, { buildContext: context })
    })
  },

  buildPromptFromContext(context) {
    const details = context.details || {}
    const talents = details.talents || {}
    const gearRows = (details.gear && details.gear.gear) || []
    const statRows = (details.statWeights && details.statWeights.stats) || []
    const simulatorState = context.simulatorState || {}
    const talentState = simulatorState.talent || {}
    const gearState = simulatorState.gear || {}
    const selectedTalentNodes = Array.isArray(talentState.selectedNodes) ? talentState.selectedNodes.join('、') : ''
    const gearNames = gearRows.slice(0, 4).map((item) => `${item.slot || '装备'}：${item.name}`).join('；')
    const stats = statRows.slice(0, 4).map((item) => item.name).join(' > ')
    return [
      `我从职业专精页带入了${context.specName || ''}${context.className || ''}的${context.activeQueryTitle || '构筑方案'}。`,
      talentState.simcHint ? `请按${talentState.simcHint}场景，先确认这个方案能否生成 SimC 任务。` : '请按大秘境多目标场景，先确认这个方案能否生成 SimC 任务。',
      talents.importCode ? `天赋导入代码：${talents.importCode}` : '',
      selectedTalentNodes ? `前端天赋模拟器已选择节点：${selectedTalentNodes}` : '',
      talentState.summary ? `天赋模拟摘要：${talentState.summary}` : '',
      gearNames ? `装备候选：${gearNames}` : '',
      gearState.progressText ? `装备获取进度：${gearState.progressText}` : '',
      gearState.nextAction ? `装备下一步：${gearState.nextAction}` : '',
      stats ? `属性趋势：${stats}` : '',
      context.analysisWindow ? `样本窗口：${context.analysisWindow}` : ''
    ].filter(Boolean).join('\n')
  },

  updateChatInput(event) {
    this.setData({ chatInput: event.detail.value || '' })
  },

  useQuickReply(event) {
    const reply = event.currentTarget.dataset.reply || ''
    if (!reply) return
    this.setData({
      latestAnalysis: this.data.latestAnalysis
        ? {
            ...this.data.latestAnalysis,
            agent: this.data.latestAnalysis.agent
              ? { ...this.data.latestAnalysis.agent, quickReplies: [] }
              : this.data.latestAnalysis.agent
          }
        : this.data.latestAnalysis
    })
    this.sendChatContent(reply)
  },

  buildConversationPrompt(messages) {
    return messages
      .filter((message) => message.role === 'user')
      .map((message, index) => `第${index + 1}轮玩家：${message.text}`)
      .join('\n')
  },

  aiTextFromAnalysis(payload) {
    const agent = payload && payload.agent
    if (!agent) return '还缺职业专精或目标场景。请直接描述你玩的专精、装等，以及想看单体、AOE、属性收益还是装备对比。'
    const profileSource = payload.request && payload.request.profileSource
    if (agent.status === 'confirmation_failed') {
      return agent.question || '后端暂时无法完成 SimC 需求确认，请稍后重试。'
    }
    if (profileSource === 'generated' && (agent.status === 'template_ready' || (agent.validation && agent.validation.passed))) {
      return '需求已确认，当前是 SimC 模板预览。需要天赋导入码和手选装备数据后才会执行正式 DPS 模拟。'
    }
    if (profileSource === 'assembled' && agent.status === 'template_ready') {
      return '需求、天赋和手选装备已确认，可以提交执行 SimC。'
    }
    if (agent.status === 'template_ready' || (agent.validation && agent.validation.passed)) {
      return '需求和角色导出输入已确认，可以提交执行 SimC。'
    }
    if (agent.question) return agent.question
    const recommendation = payload.recommendations && payload.recommendations[0]
    return recommendation || '还需要补充职业专精、模拟场景或比较目标。'
  },

  isTaskReady(payload) {
    const agent = payload && payload.agent
    return !!(agent && (agent.canSubmitTask || agent.status === 'template_ready' || (agent.validation && agent.validation.passed)))
  },

  appendMessages(items, extraData) {
    const start = this.data.messageSeq
    const nextMessages = items.map((item, index) => ({
      id: `msg-${start + index}`,
      role: item.role,
      text: item.text
    }))
    this.setData({
      ...(extraData || {}),
      messages: this.data.messages.concat(nextMessages),
      messageSeq: start + nextMessages.length,
      chatAnchor: 'chat-bottom'
    })
  },

  sendChatMessage() {
    const content = (this.data.chatInput || '').trim()
    this.sendChatContent(content)
  },

  sendChatContent(content, options) {
    if (!content || this.data.loadingChat || this.data.canSubmitTask || this.data.taskSubmitted) return

    const requestOptions = options || {}
    const nextRound = this.data.conversationRound + 1
    const userMessage = { id: `msg-${this.data.messageSeq}`, role: 'user', text: content }
    const nextMessages = this.data.messages.concat([userMessage])
    const prompt = this.buildConversationPrompt(nextMessages)
    this.setData({
      messages: nextMessages,
      messageSeq: this.data.messageSeq + 1,
      chatInput: '',
      chatAnchor: 'chat-bottom',
      loadingChat: true,
      latestAnalysis: this.data.latestAnalysis
        ? {
            ...this.data.latestAnalysis,
            agent: this.data.latestAnalysis.agent
              ? { ...this.data.latestAnalysis.agent, quickReplies: [] }
              : this.data.latestAnalysis.agent
          }
        : this.data.latestAnalysis
    })

    const requestPayload = {
      mode: 'simcraft_agent',
      message: prompt,
      prompt,
      round: nextRound,
      conversationRound: nextRound,
      confirmOnly: true,
      buildContext: this.data.pendingBuildContext
    }
    if (requestOptions.buildContext) requestPayload.buildContext = requestOptions.buildContext
    if (!requestPayload.buildContext) delete requestPayload.buildContext

    requestSimulatorAnalysis(requestPayload).then(({ payload, fromFallback, error }) => {
      const ready = this.isTaskReady(payload)
      this.appendMessages([
        { role: 'ai', text: this.aiTextFromAnalysis(payload) }
      ], {
        latestAnalysis: payload,
        fromFallback,
        requestError: error || '',
        conversationRound: nextRound,
        canSubmitTask: ready,
        confirmedPrompt: ready ? prompt : this.data.confirmedPrompt
      })
    }).finally(() => {
      this.setData({ loadingChat: false })
    })
  },

  submitConfirmedTask() {
    if (!this.data.canSubmitTask || this.data.submittingTask || this.data.taskSubmitted) return
    this.setData({ submittingTask: true })
    loginWithWechat().catch(() => null).then(() => {
      return requestSimulatorAnalysis({
        mode: 'simcraft_agent',
        message: this.data.confirmedPrompt,
        prompt: this.data.confirmedPrompt,
        round: this.data.conversationRound,
        runSimulation: true,
        saveTask: true,
        buildContext: this.data.pendingBuildContext
      }, { auth: true, allowInsecureGuestRequest: true })
    }).then(({ payload, fromFallback, error }) => {
      const saved = !!(payload && payload.taskId)
      this.appendMessages([
        { role: 'ai', text: saved ? '任务已提交，结果会保存到任务列表。' : '提交失败，未保存到任务列表。请稍后重试。' }
      ], {
        latestAnalysis: payload,
        fromFallback,
        requestError: error || '',
        taskSubmitted: saved,
        submittedTaskId: (payload && payload.taskId) || '',
        canSubmitTask: !saved
      })
      wx.showToast({ title: saved ? '任务已提交' : '提交失败', icon: 'none' })
    }).finally(() => {
      this.setData({ submittingTask: false })
    })
  }
})
