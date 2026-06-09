const { requestJson } = require('../common/api-client')

function fallbackSimulatorHome() {
  return {
    navTitle: '模拟器',
    kicker: '能力 04',
    title: '构筑模拟器与 AI 分析',
    desc: '提供 AI 辅助能力，帮助玩家跑 SimCraft、分析 WCL 数据、比较配装收益和定位输出问题。',
    metrics: [
      { value: 'Prompt', label: 'LLM' },
      { value: '待安装', label: 'SimCraft' },
      { value: 'WCL', label: '日志复盘' }
    ],
    quickActions: [
      { key: 'simcraft', title: '跑 SimCraft', desc: '比较装备、天赋和属性收益' },
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
    capabilities: {
      simcraft: false,
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
    }
  }
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
    auth: true,
    timeout: 15000,
    fallback: () => fallbackSimulatorAnalysis(request),
    validate: (data) => data && data.status && data.recommendations
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
  fallbackSimulatorAnalysis,
  fallbackSimulatorHome,
  requestSimulatorAnalysis,
  requestSimulatorHome,
  requestSimulatorTasks
}
