const { requestJson } = require('../common/api-client')

const SIMULATOR_GUEST_ID_STORAGE_KEY = 'wow_simulator_guest_id'

function randomGuestId() {
  return `guest-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function simulatorGuestId() {
  if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return randomGuestId()
  const stored = wx.getStorageSync(SIMULATOR_GUEST_ID_STORAGE_KEY)
  if (stored) return stored
  const nextGuestId = randomGuestId()
  if (typeof wx.setStorageSync === 'function') wx.setStorageSync(SIMULATOR_GUEST_ID_STORAGE_KEY, nextGuestId)
  return nextGuestId
}

function attachGuestId(request, requestOptions) {
  const payload = { ...(request || {}) }
  if (requestOptions.auth && requestOptions.allowInsecureGuestRequest && payload.saveTask) {
    payload.guestId = simulatorGuestId()
  }
  return payload
}

function guestQueryString() {
  return `guest=1&guestId=${encodeURIComponent(simulatorGuestId())}`
}

function fallbackAgentQuickReplies(request) {
  const prompt = String((request && (request.message || request.prompt)) || '')
  if (/术士|warlock/i.test(prompt)) {
    return ['我是痛苦术，看大秘境 AOE', '我是恶魔术，看大秘境 AOE', '我是毁灭术，看大秘境 AOE']
  }
  if (/法师|mage/i.test(prompt)) {
    return ['我是冰法，看单体属性收益', '我是火法，看大秘境 AOE', '我是奥法，看单体 DPS']
  }
  if (/萨满|shaman/i.test(prompt)) {
    return ['我是元素萨，看大秘境 AOE', '我是增强萨，看大秘境 AOE']
  }
  return ['我是冰法，看单体属性收益', '我是元素萨，看大秘境 AOE', '我是恶魔术，看大秘境 AOE']
}

function fallbackSimulatorHome() {
  return {
    navTitle: '智能分析',
    kicker: '能力 04',
    title: '智能分析',
    desc: '把模拟、日志复盘和历史任务收束到同一个入口，先选择分析类型，再进入对应工作台。',
    analysisModules: [
      {
        key: 'simc',
        badge: '01',
        title: '模拟 SimC',
        desc: '用中文描述职业专精、装等和目标场景，进入专属工作台生成模拟结论。',
        action: '进入模拟'
      },
      {
        key: 'wcl',
        badge: '02',
        title: '分析 WCL',
        desc: '提交战斗日志链接和问题，复盘输出、爆发、覆盖率与关键失误。',
        action: '进入分析'
      },
      {
        key: 'tasks',
        badge: '03',
        title: '任务列表',
        desc: '查看最近提交过的模拟和日志分析任务，继续追踪结果。',
        action: '查看记录'
      }
    ],
    quickActions: [
      { key: 'simc', title: '模拟 SimC', desc: '进入 SimC 工作台' },
      { key: 'wcl', title: '分析 WCL', desc: '进入 WCL 工作台' },
      { key: 'tasks', title: '任务列表', desc: '查看最近任务' }
    ],
    tasks: [
      { title: 'SimC 智能模拟', status: '可提交', desc: '描述职业专精、装等和目标场景，生成 SimCraft 和 AI 分析请求。' },
      { title: 'WCL 战斗日志分析', status: '可分析', desc: '用 AI 总结输出差距、技能覆盖和关键失误。' }
    ],
    capabilities: {
      simcraft: false,
      llm: false,
      wcl: true
    }
  }
}

function defaultAnalysisModules() {
  return fallbackSimulatorHome().analysisModules
}

function normalizeSimulatorHomePayload(payload) {
  const home = payload || fallbackSimulatorHome()
  return {
    ...home,
    navTitle: '智能分析',
    title: home.title === 'SimC Agent 与构筑分析' ? '智能分析' : (home.title || '智能分析'),
    desc: home.desc || fallbackSimulatorHome().desc,
    analysisModules: Array.isArray(home.analysisModules) && home.analysisModules.length
      ? home.analysisModules
      : defaultAnalysisModules(),
    quickActions: Array.isArray(home.quickActions) && home.quickActions.length
      ? home.quickActions
      : fallbackSimulatorHome().quickActions,
    metrics: undefined
  }
}

function fallbackSimulatorAnalysis(request) {
  return {
    mode: (request && request.mode) || 'simcraft',
    status: 'ready',
    request: {
      prompt: (request && request.prompt) || '',
      message: (request && request.message) || '',
      runSimulation: !!(request && request.runSimulation)
    },
    agent: {
      status: 'needs_clarification',
      round: (request && request.round) || 1,
      intent: 'baseline',
      missingSlots: ['specialization'],
      question: '先告诉我职业和专精，再说想看单体、AOE、属性收益、天赋还是装备对比。',
      quickReplies: fallbackAgentQuickReplies(request),
      draftProfile: '',
      validation: {
        passed: false,
        errors: ['missing specialization'],
        warnings: []
      },
      summaryCards: []
    },
    stages: [
      {
        key: 'profile_check',
        title: 'Profile 检查',
        status: 'blocked',
        executor: 'backend',
        summary: '本地兜底模式无法校验完整 profile'
      },
      {
        key: 'simc_execution',
        title: 'SimC 执行',
        status: 'skipped',
        executor: 'simcraft',
        summary: '未连接后端，未执行服务器 SimC',
        metric: ''
      },
      {
        key: 'ai_interpretation',
        title: 'AI 解读',
        status: 'skipped',
        executor: 'llm',
        summary: '未连接后端，未调用 LLM'
      }
    ],
    simulation: {
      ran: false,
      available: false,
      summary: '',
      error: 'using local fallback'
    },
    capabilities: {
      simcraft: false,
      codex: false,
      llm: false
    },
    recommendations: [
      '先补充职业专精、装等、目标场景和想解决的问题，后端会据此生成模板。',
      '如果是 WCL 复盘，请补充具体战斗链接、难度、boss 和想解决的问题。'
    ],
    llm: {
      prompt: '',
      called: false,
      model: '',
      content: '',
      error: 'missing api base url'
    },
    codex: {
      enabled: false,
      called: false,
      status: 'disabled',
      jobId: '',
      lastMessage: '',
      error: 'missing api base url'
    }
  }
}

function agentClarificationPayload(request) {
  const prompt = (request && (request.message || request.prompt)) || ''
  return {
    mode: 'simcraft_agent',
    status: 'ready',
    request: {
      prompt,
      message: prompt,
      runSimulation: false
    },
    agent: {
      status: 'needs_clarification',
      round: (request && request.round) || 1,
      intent: 'baseline',
      missingSlots: ['specialization'],
      question: '先告诉我职业和专精，再说想看单体、AOE、属性收益、天赋还是装备对比。',
      quickReplies: fallbackAgentQuickReplies(request),
      draftProfile: '',
      validation: {
        passed: false,
        errors: ['missing specialization'],
        warnings: []
      },
      summaryCards: [
        { title: '结论', text: '本次没有执行真实 SimC：缺少职业专精。' },
        { title: '下一步', text: '请补充职业专精、装等和目标场景。' }
      ]
    },
    stages: [
      {
        key: 'profile_check',
        title: 'Profile 检查',
        status: 'blocked',
        executor: 'backend',
        summary: '缺少职业专精'
      },
      {
        key: 'simc_execution',
        title: 'SimC 执行',
        status: 'skipped',
        executor: 'simcraft',
        summary: 'missing specialization',
        metric: ''
      },
      {
        key: 'ai_interpretation',
        title: 'AI 解读',
        status: 'skipped',
        executor: 'llm',
        summary: '等待补充职业专精和目标场景'
      }
    ],
    simulation: {
      ran: false,
      available: false,
      summary: '',
      error: 'missing specialization'
    },
    capabilities: {
      simcraft: false,
      codex: false,
      llm: false
    },
    recommendations: [
      '先告诉我职业和专精，再说想看单体、AOE、属性收益、天赋还是装备对比。'
    ],
    llm: {
      prompt: '',
      called: false,
      model: '',
      content: '',
      error: ''
    },
    codex: {
      enabled: false,
      called: false,
      status: 'skipped',
      jobId: '',
      lastMessage: '',
      error: 'missing specialization'
    }
  }
}

function isLegacyEmptyProfileAgentResponse(request, payload) {
  if (!request || request.mode !== 'simcraft_agent') return false
  if (!payload || payload.agent) return false
  const simulationError = payload.simulation && payload.simulation.error
  const simcStage = (payload.stages || []).find((stage) => stage && stage.key === 'simc_execution')
  return simulationError === 'empty profile' || (simcStage && simcStage.summary === 'empty profile')
}

function isLegacyMissingAgentResponse(request, payload) {
  if (!request || request.mode !== 'simcraft_agent') return false
  if (!payload || payload.agent) return false
  if (payload.taskId) return false
  return true
}

function normalizeSimulatorAnalysisPayload(request, payload) {
  if (isLegacyEmptyProfileAgentResponse(request, payload) || isLegacyMissingAgentResponse(request, payload)) {
    return agentClarificationPayload(request)
  }
  return payload
}

function requestSimulatorHome() {
  return requestJson('/api/simulator/home', {
    fallback: fallbackSimulatorHome,
    validate: (data) => data && data.navTitle && data.quickActions
  }).then((result) => {
    return {
      ...result,
      payload: normalizeSimulatorHomePayload(result.payload)
    }
  })
}

function requestSimulatorAnalysis(request, options) {
  const requestOptions = options || {}
  const requestPayload = attachGuestId(request, requestOptions)
  return requestJson('/api/simulator/analyze', {
    method: 'POST',
    data: requestPayload,
    auth: !!requestOptions.auth,
    allowInsecureGuestRequest: !!requestOptions.allowInsecureGuestRequest,
    timeout: 90000,
    fallback: () => fallbackSimulatorAnalysis(requestPayload),
    validate: (data) => data && data.status && data.recommendations
  }).then((result) => {
    return {
      ...result,
      payload: normalizeSimulatorAnalysisPayload(requestPayload, result.payload)
    }
  })
}

function requestSimulatorTasks() {
  return requestJson(`/api/simulator/tasks?${guestQueryString()}`, {
    auth: true,
    allowInsecureGuestRequest: true,
    fallback: () => ({ tasks: [] }),
    validate: (data) => data && Array.isArray(data.tasks)
  })
}

function requestSimulatorTaskDetail(taskId) {
  const encodedTaskId = encodeURIComponent(taskId || '')
  return requestJson(`/api/simulator/task?id=${encodedTaskId}&${guestQueryString()}`, {
    auth: true,
    allowInsecureGuestRequest: true,
    fallback: () => ({ task: null }),
    validate: (data) => data && data.task && data.task.taskId
  })
}

module.exports = {
  agentClarificationPayload,
  fallbackSimulatorAnalysis,
  fallbackSimulatorHome,
  normalizeSimulatorAnalysisPayload,
  requestSimulatorAnalysis,
  requestSimulatorHome,
  requestSimulatorTaskDetail,
  requestSimulatorTasks,
  SIMULATOR_GUEST_ID_STORAGE_KEY
}
