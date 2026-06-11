const { loginWithWechat } = require('../common/auth-client')
const {
  requestSimulatorAnalysis
} = require('./simulator-api')

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
    fromFallback: true,
    requestError: '',
    latestAnalysis: null
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
    if (agent.status === 'template_ready' || (agent.validation && agent.validation.passed)) {
      return '需求已确认，可以转成 SimC 模板。现在可以提交任务。'
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

  sendChatContent(content) {
    if (!content || this.data.loadingChat || this.data.canSubmitTask || this.data.taskSubmitted) return

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

    requestSimulatorAnalysis({
      mode: 'simcraft_agent',
      message: prompt,
      prompt,
      round: nextRound,
      conversationRound: nextRound,
      confirmOnly: true
    }).then(({ payload, fromFallback, error }) => {
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
        saveTask: true
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
