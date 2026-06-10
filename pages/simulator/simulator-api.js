const { requestJson } = require('../common/api-client')

function fallbackSimulatorHome() {
  return {
    navTitle: '模拟器',
    kicker: '能力 04',
    title: 'SimC Agent 与构筑分析',
    desc: '用普通语言描述模拟目标，后端负责澄清需求、生成 SimC 模板、执行模拟并总结结论。',
    metrics: [
      { value: 'Prompt', label: 'LLM' },
      { value: '待安装', label: 'SimCraft' },
      { value: 'WCL', label: '日志复盘' }
    ],
    quickActions: [
      { key: 'simcraft', title: 'SimC Agent', desc: '普通话描述需求，自动生成模拟模板' },
      { key: 'wcl', title: '分析 WCL', desc: '定位循环、爆发和减员问题' },
      { key: 'gearCompare', title: '配装对比', desc: '多套装备收益横向比较' },
      { key: 'llmAdvice', title: 'AI 建议', desc: '生成可执行优化建议' }
    ],
    tasks: [
      { title: '导入角色构筑', status: '可提交', desc: '粘贴角色数据，生成 SimCraft 和 AI 分析请求。' },
      { title: 'WCL 战斗日志分析', status: 'LLM', desc: '用 AI 总结输出差距、技能覆盖和关键失误。' }
    ],
    capabilities: {
      simcraft: false,
      llm: false,
      wcl: true
    }
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
      missingSlots: ['character_source'],
      question: '要做准确 SimC，请粘贴游戏内 /simc 插件导出，或提供角色名、服务器和地区。',
      quickReplies: ['粘贴 /simc 导出', '提供角色名服务器', '只生成待补齐模板'],
      draftProfile: '',
      validation: {
        passed: false,
        errors: ['missing character source'],
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
      '先补充角色、专精、目标场景和 SimCraft profile，后端可据此生成更准确的分析。',
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
      missingSlots: ['character_source'],
      question: '要做准确 SimC，需要角色数据来源。请粘贴游戏内 /simc 插件导出，或提供角色名、服务器和地区。',
      quickReplies: ['粘贴 /simc 导出', '提供角色名服务器', '只生成待补齐模板'],
      draftProfile: '',
      validation: {
        passed: false,
        errors: ['missing character source'],
        warnings: []
      },
      summaryCards: [
        { title: '结论', text: '本次没有执行真实 SimC：缺少角色数据来源。' },
        { title: '下一步', text: '请补充 /simc 导出或角色名、服务器和地区。' }
      ]
    },
    stages: [
      {
        key: 'profile_check',
        title: 'Profile 检查',
        status: 'blocked',
        executor: 'backend',
        summary: '缺少角色数据来源'
      },
      {
        key: 'simc_execution',
        title: 'SimC 执行',
        status: 'skipped',
        executor: 'simcraft',
        summary: 'missing character source',
        metric: ''
      },
      {
        key: 'ai_interpretation',
        title: 'AI 解读',
        status: 'skipped',
        executor: 'llm',
        summary: '等待补充角色数据'
      }
    ],
    simulation: {
      ran: false,
      available: false,
      summary: '',
      error: 'missing character source'
    },
    capabilities: {
      simcraft: false,
      codex: false,
      llm: false
    },
    recommendations: [
      '要做准确 SimC，需要角色数据来源。请粘贴游戏内 /simc 插件导出，或提供角色名、服务器和地区。'
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
      error: 'missing character source'
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

function normalizeSimulatorAnalysisPayload(request, payload) {
  if (isLegacyEmptyProfileAgentResponse(request, payload)) {
    return agentClarificationPayload(request)
  }
  return payload
}

function requestSimulatorHome() {
  return requestJson('/api/simulator/home', {
    fallback: fallbackSimulatorHome,
    validate: (data) => data && data.navTitle && data.quickActions
  })
}

function requestSimulatorAnalysis(request) {
  return requestJson('/api/simulator/analyze', {
    method: 'POST',
    data: request || {},
    timeout: 90000,
    fallback: () => fallbackSimulatorAnalysis(request),
    validate: (data) => data && data.status && data.recommendations
  }).then((result) => {
    return {
      ...result,
      payload: normalizeSimulatorAnalysisPayload(request || {}, result.payload)
    }
  })
}

function requestSimulatorTasks() {
  return requestJson('/api/simulator/tasks', {
    auth: true,
    fallback: () => ({ tasks: [] }),
    validate: (data) => data && Array.isArray(data.tasks)
  })
}

module.exports = {
  agentClarificationPayload,
  fallbackSimulatorAnalysis,
  fallbackSimulatorHome,
  normalizeSimulatorAnalysisPayload,
  requestSimulatorAnalysis,
  requestSimulatorHome,
  requestSimulatorTasks
}
