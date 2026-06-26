const { requestJson } = require('../common/api-client')

const SIMULATOR_GUEST_ID_STORAGE_KEY = 'wow_simulator_guest_id'
const FIRST_VERSION_ANALYSIS_KEYS = ['chickenbro']

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

function fallbackSimulatorHome() {
  return {
    navTitle: '智能分析',
    kicker: '能力 04',
    title: '智能分析',
    desc: '首版智能分析只保留炸鸡队长，围绕已有证据给出下一步建议。',
    analysisModules: [
      {
        key: 'chickenbro',
        badge: '01',
        title: '炸鸡队长',
        desc: '把已有 SimC 与角色上下文整理成证据受限的下一步建议，缺证据时只列缺失项。',
        action: '进入教练'
      }
    ],
    quickActions: [
      { key: 'chickenbro', title: '炸鸡队长', desc: '进入证据教练' }
    ],
    capabilities: {
      simcraft: false,
      llm: false,
      wcl: false
    }
  }
}

function defaultAnalysisModules() {
  return fallbackSimulatorHome().analysisModules
}

function normalizeSimulatorHomePayload(payload) {
  const home = payload || fallbackSimulatorHome()
  const { metrics, ...homeWithoutLegacyMetrics } = home
  const modules = Array.isArray(home.analysisModules) && home.analysisModules.length
    ? home.analysisModules
    : defaultAnalysisModules()
  const quickActions = Array.isArray(home.quickActions) && home.quickActions.length
    ? home.quickActions
    : fallbackSimulatorHome().quickActions
  return {
    ...homeWithoutLegacyMetrics,
    navTitle: '智能分析',
    title: home.title === 'SimC Agent 与构筑分析' ? '智能分析' : (home.title || '智能分析'),
    desc: home.desc || fallbackSimulatorHome().desc,
    analysisModules: modules.filter((module) => FIRST_VERSION_ANALYSIS_KEYS.includes(module && module.key)),
    quickActions: quickActions.filter((action) => FIRST_VERSION_ANALYSIS_KEYS.includes(action && action.key)),
    capabilities: {
      ...(home.capabilities || {}),
      wcl: false
    }
  }
}

function unavailableSimulatorAnalysis(request, reason) {
  const prompt = (request && (request.message || request.prompt)) || ''
  return {
    mode: (request && request.mode) || 'simcraft',
    status: 'ready',
    request: {
      prompt,
      message: prompt,
      runSimulation: false
    },
    agent: {
      status: 'confirmation_failed',
      round: (request && request.round) || 1,
      intent: 'baseline',
      missingSlots: [],
      question: '后端暂时无法完成 SimC 需求确认，请稍后重试。',
      quickReplies: [],
      draftProfile: '',
      validation: {
        passed: false,
        errors: ['backend confirmation unavailable'],
        warnings: reason ? [reason] : []
      },
      summaryCards: []
    },
    stages: [
      {
        key: 'profile_check',
        title: 'Profile 检查',
        status: 'failed',
        executor: 'backend',
        summary: '后端确认不可用'
      },
      {
        key: 'simc_execution',
        title: 'SimC 执行',
        status: 'skipped',
        executor: 'simcraft',
        summary: '需求未确认，未执行服务器 SimC',
        metric: ''
      },
      {
        key: 'ai_interpretation',
        title: 'AI 解读',
        status: 'failed',
        executor: 'llm',
        summary: '后端 LLM 确认不可用'
      }
    ],
    simulation: {
      ran: false,
      available: false,
      summary: '',
      error: reason || 'backend confirmation unavailable'
    },
    capabilities: {
      simcraft: false,
      codex: false,
      llm: false
    },
    recommendations: [
      '后端暂时无法完成 SimC 需求确认，请稍后重试。'
    ],
    llm: {
      prompt: '',
      called: false,
      model: '',
      content: '',
      error: reason || 'backend confirmation unavailable'
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

function fallbackSimulatorAnalysis(request) {
  return unavailableSimulatorAnalysis(request, 'backend confirmation unavailable')
}

function agentClarificationPayload(request) {
  return unavailableSimulatorAnalysis(request, 'legacy backend response missing agent')
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

function fallbackChickenbroMessage(request) {
  return {
    mode: 'chickenbro',
    session: { sessionId: request && request.sessionId ? request.sessionId : '' },
    job: { jobId: '', status: 'failed' },
    userMessage: {
      role: 'user',
      content: (request && request.message) || ''
    },
    assistantMessage: {
      role: 'assistant',
      content: '后端暂时无法连接炸鸡队长，请稍后重试；当前不会使用本地假结论替代真实证据链。',
      payload: {
        answerSource: 'frontend_fallback',
        confidence: 'blocked',
        priorityActions: [],
        evidenceRefs: [],
        limitations: ['backend unavailable']
      }
    }
  }
}

function requestChickenbroMessage(request) {
  const payload = {
    ...(request || {}),
    guestId: simulatorGuestId()
  }
  return requestJson('/api/chickenbro/messages', {
    method: 'POST',
    data: payload,
    auth: true,
    allowInsecureGuestRequest: true,
    timeout: 90000,
    fallback: () => fallbackChickenbroMessage(payload),
    validate: (data) => data && data.mode === 'chickenbro' && data.session && data.assistantMessage
  })
}

function requestChickenbroSession(sessionId) {
  const encodedSessionId = encodeURIComponent(sessionId || '')
  return requestJson(`/api/chickenbro/sessions?id=${encodedSessionId}&${guestQueryString()}`, {
    auth: true,
    allowInsecureGuestRequest: true,
    fallback: () => ({ session: null, messages: [] }),
    validate: (data) => data && data.session && Array.isArray(data.messages)
  })
}

function requestChickenbroJob(jobId) {
  const encodedJobId = encodeURIComponent(jobId || '')
  return requestJson(`/api/chickenbro/jobs?id=${encodedJobId}&${guestQueryString()}`, {
    auth: true,
    allowInsecureGuestRequest: true,
    fallback: () => ({ job: null }),
    validate: (data) => data && data.job && data.job.jobId
  })
}

module.exports = {
  agentClarificationPayload,
  fallbackSimulatorAnalysis,
  fallbackSimulatorHome,
  requestChickenbroJob,
  requestChickenbroMessage,
  requestChickenbroSession,
  normalizeSimulatorAnalysisPayload,
  requestSimulatorAnalysis,
  requestSimulatorHome,
  requestSimulatorTaskDetail,
  requestSimulatorTasks,
  SIMULATOR_GUEST_ID_STORAGE_KEY
}
