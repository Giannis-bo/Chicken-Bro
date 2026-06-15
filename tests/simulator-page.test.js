const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('simc page uses chat clarification before task submission', () => {
  const js = fs.readFileSync('pages/simulator/simc.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')

  assert.match(wxml, /chat-messages/)
  assert.match(wxml, /chat-context/)
  assert.doesNotMatch(wxml, /<view class="hero simulator-hero">/)
  assert.match(wxml, /wx:for="\{\{messages\}\}"/)
  assert.match(wxml, /chat-row-\{\{item\.role\}\}/)
  assert.match(wxml, /value="\{\{chatInput\}\}"/)
  assert.match(wxml, /bindinput="updateChatInput"/)
  assert.match(wxml, /bindtap="sendChatMessage"/)
  assert.match(wxml, /bindtap="submitConfirmedTask"/)
  assert.match(wxml, /disabled="\{\{!canSubmitTask \|\| submittingTask \|\| taskSubmitted\}\}"/)
  assert.match(wxml, /任务已提交/)
  assert.doesNotMatch(wxml, /最多\s*3\s*轮/)
  assert.match(js, /messages:\s*\[/)
  assert.doesNotMatch(js, /maxRounds:\s*3/)
  assert.doesNotMatch(js, /conversationRound\s*>=\s*this\.data\.maxRounds/)
  assert.doesNotMatch(js, /chatLocked/)
  assert.match(js, /sendChatMessage\(\)/)
  assert.match(js, /sendChatContent\(content\)/)
  assert.match(js, /submitConfirmedTask\(\)/)
  assert.match(js, /confirmOnly:\s*true/)
  assert.match(js, /saveTask:\s*true/)
  assert.match(js, /allowInsecureGuestRequest:\s*true/)
  assert.match(js, /canSubmitTask/)
  assert.match(js, /taskSubmitted/)
  assert.match(js, /auth:\s*true/)
  assert.doesNotMatch(js, /\/simc|角色名|服务器|角色数据/)
  assert.doesNotMatch(wxml, /\/simc|角色名|服务器|角色数据/)
  assert.match(js, /mode:\s*'simcraft_agent'/)
  assert.match(js, /runSimulation:\s*true/)
  assert.match(css, /\.chat-row-user/)
  assert.match(css, /\.chat-row-ai/)
  assert.match(css, /\.chat-composer/)
  assert.match(css, /\.send-button[\s\S]*width:\s*132rpx;/)
  assert.match(css, /\.task-submit-button\[disabled\]/)
  assert.match(css, /\.submit-button/)
  assert.match(css, /\.submit-ready/)
})

test('simc quick replies are sent immediately and clear stale suggestions', () => {
  const js = fs.readFileSync('pages/simulator/simc.js', 'utf8')

  assert.match(js, /useQuickReply\(event\)/)
  assert.match(js, /this\.sendChatContent\(reply\)/)
  assert.match(js, /quickReplies:\s*\[\]/)
  assert.doesNotMatch(js, /useQuickReply\(event\)[\s\S]{0,180}setData\(\{\s*chatInput:\s*reply\s*\}\)/)
})

test('simc confirmation explains generated templates are preview-only', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/simc.js')]
  require('../pages/simulator/simc.js')
  global.Page = originalPage

  const text = pageDefinition.aiTextFromAnalysis({
    request: { profileSource: 'generated' },
    agent: {
      status: 'template_ready',
      validation: { passed: true }
    },
    recommendations: ['需求已确认，可以提交 SimC 任务。']
  })

  assert.match(text, /模板预览/)
  assert.match(text, /天赋导入码和手选装备数据/)
  assert.doesNotMatch(text, /现在可以提交任务/)
})

test('simc page loads build context from specialization detail and confirms it', () => {
  const js = fs.readFileSync('pages/simulator/simc.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')

  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /onLoad\(options\)/)
  assert.match(js, /loadBuildContext\(options\)/)
  assert.match(js, /wx\.getStorageSync\(SIMC_BUILD_CONTEXT_STORAGE_KEY\)/)
  assert.match(js, /buildPromptFromContext\(context\)/)
  assert.match(js, /this\.sendChatContent\(prompt,\s*\{ buildContext: context \}\)/)
  assert.match(js, /pendingBuildContext/)
  assert.match(js, /buildContext:\s*this\.data\.pendingBuildContext/)
  assert.match(wxml, /context-source/)
  assert.match(wxml, /buildContextTitle/)
})

test('simc prompt includes front-end talent and gear simulator state', () => {
  const js = fs.readFileSync('pages/simulator/simc.js', 'utf8')

  assert.match(js, /context\.simulatorState \|\| \{\}/)
  assert.match(js, /talentState\.selectedNodes/)
  assert.match(js, /talentState\.simcHint/)
  assert.match(js, /formatTalentNodeLabel/)
  assert.match(js, /talentState\.websimExportCode/)
  assert.match(js, /talentState\.encodingStatus/)
  assert.match(js, /gearState\.progressText/)
  assert.match(js, /gearState\.nextAction/)
})

test('simc prompt formats WebSim talent node objects and encoding lines', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/simc.js')]
  require('../pages/simulator/simc.js')
  global.Page = originalPage

  const prompt = pageDefinition.buildPromptFromContext({
    specId: '法师-冰霜',
    className: '法师',
    specName: '冰霜',
    activeQueryTitle: '天赋构筑',
    details: {
      talents: {
        importCode: 'CAE_CONTEXT',
        simcLines: ['class_talents=1001:1', 'spec_talents=2001:2'],
        encodingStatus: 'encoded'
      }
    },
    simulatorState: {
      talent: {
        selectedNodes: [
          { id: 'n1', name: 'Ice Lance', rank: 2, tree: 'spec' },
          { id: 'n2', name: 'Spellslinger', rank: 1, tree: 'hero' }
        ],
        websimExportCode: 'websim:mage:frost:spellslinger:n1:2,n2:1',
        heroKey: 'spellslinger',
        scenarioKey: 'mythic_plus',
        encodingStatus: 'encoded'
      }
    }
  })

  assert.match(prompt, /前端天赋模拟器已选择节点：Ice Lance x2、Spellslinger/)
  assert.match(prompt, /WebSim 导出码：websim:mage:frost:spellslinger:n1:2,n2:1/)
  assert.match(prompt, /WebSim 天赋编码：encoded/)
  assert.match(prompt, /SimC 天赋行：class_talents=1001:1；spec_talents=2001:2/)
  assert.doesNotMatch(prompt, /\[object Object\]/)
})

test('simulator page renders simc agent clarification and summary cards', () => {
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')

  assert.match(wxml, /SimC 需求确认/)
  assert.match(wxml, /latestAnalysis\.agent\.quickReplies/)
  assert.doesNotMatch(wxml, /确认摘要/)
  assert.doesNotMatch(wxml, /生成的 SimC 模板/)
  assert.doesNotMatch(wxml, /latestAnalysis\.agent\.summaryCards/)
  assert.doesNotMatch(wxml, /latestAnalysis\.agent\.draftProfile/)
  assert.match(api, /agent:\s*\{/)
  assert.match(api, /confirmation_failed/)
  assert.doesNotMatch(api, /我是冰法|我是元素萨|我是恶魔术/)
  assert.match(css, /\.quick-reply/)
  assert.doesNotMatch(css, /\.agent-summary-list/)
  assert.doesNotMatch(css, /\.agent-template/)
})

test('simulator page uses a dark code-console visual treatment', () => {
  const wxml = fs.readFileSync('pages/simulator/simc.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simc.wxss', 'utf8')

  assert.match(wxml, /background="#111111"/)
  assert.match(css, /\.chat-context[\s\S]*#493477/i)
  assert.match(css, /\.chat-input[\s\S]*background:\s*#101010;/)
  assert.match(css, /\.chat-input[\s\S]*color:\s*#e1e2e5;/)
  assert.match(css, /\.submit-button[\s\S]*background:\s*#8b3ff5;/)
})

test('smart analysis tab is a three-module entry hub without metrics', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/simulator.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/simc'))
  assert.ok(app.pages.includes('pages/simulator/wcl'))
  assert.ok(app.pages.includes('pages/simulator/task-detail'))
  assert.match(wxml, /<view class="hero simulator-hero">/)
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
  assert.match(wxml, /analysis-modules/)
  assert.match(wxml, /wx:for="\{\{analysisModules\}\}"/)
  assert.match(wxml, /scroll-into-view="\{\{scrollTarget\}\}"/)
  assert.match(wxml, /id="task-section"/)
  assert.match(wxml, /任务列表/)
  assert.match(wxml, /data-task-id="\{\{item\.taskId\}\}"/)
  assert.match(wxml, /bindtap="openTaskDetail"/)
  assert.match(js, /openAnalysisModule\(event\)/)
  assert.match(js, /openTaskDetail\(event\)/)
  assert.match(js, /onShow\(\)\s*\{\s*this\.loadSimulatorTasks\(\)/)
  assert.match(js, /scrollTarget:\s*''/)
  assert.match(js, /scrollTarget:\s*'task-section'/)
  assert.match(js, /tasks:\s*\[\]/)
  assert.match(js, /taskId:\s*task\.taskId/)
  assert.match(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/simc/)
  assert.match(js, /wx\.navigateTo\(\{[\s\S]*\/pages\/simulator\/wcl/)
  assert.match(js, /\/pages\/simulator\/task-detail\?id=/)
  assert.match(api, /navTitle:\s*'智能分析'/)
  assert.match(api, /analysisModules:\s*\[/)
  assert.match(api, /title:\s*'模拟 SimC'/)
  assert.match(api, /title:\s*'分析 WCL'/)
  assert.match(api, /title:\s*'任务列表'/)
  assert.match(css, /\.analysis-modules/)
  assert.match(css, /\.analysis-module-card/)
})

test('simulator task detail page renders saved task analysis', () => {
  const js = fs.readFileSync('pages/simulator/task-detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/task-detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/simulator/task-detail.wxss', 'utf8')
  const api = fs.readFileSync('pages/simulator/simulator-api.js', 'utf8')

  assert.match(js, /requestSimulatorTaskDetail/)
  assert.match(js, /loadTaskDetail\(options\.id/)
  assert.match(js, /normalizeTaskDetail\(task\)/)
  assert.match(wxml, /任务详情/)
  assert.match(wxml, /玩家问题/)
  assert.match(wxml, /AI 结论/)
  assert.match(wxml, /真实大秘境对标/)
  assert.match(wxml, /执行阶段/)
  assert.doesNotMatch(wxml, /生成的 SimC 模板/)
  assert.doesNotMatch(wxml, /SimC 执行摘要/)
  assert.match(wxml, /detail\.recommendations/)
  assert.match(wxml, /detail\.mythicPlusReference/)
  assert.match(wxml, /detail\.mythicPlusReferenceText/)
  assert.match(wxml, /detail\.buildContextText/)
  assert.match(wxml, /detail\.stages/)
  assert.doesNotMatch(wxml, /detail\.draftProfile/)
  assert.doesNotMatch(wxml, /detail\.simulationSummary/)
  assert.doesNotMatch(wxml, /detail\.llmContent/)
  assert.doesNotMatch(wxml, /AI 解读/)
  assert.match(wxml, /detail\.heroTitle/)
  assert.match(wxml, /detail\.questionSummary/)
  assert.doesNotMatch(wxml, /class="detail-title">\{\{detail\.question\}\}/)
  assert.match(js, /summarizeTaskQuestion\(question\)/)
  assert.match(js, /heroTitle/)
  assert.match(js, /questionSummary/)
  assert.match(js, /simcMetricLabel/)
  assert.match(js, /simcUnitText/)
  assert.match(js, /simcDisplayValue/)
  assert.match(wxml, /detail\.simcDisplayValue/)
  assert.match(wxml, /detail\.simcMetricLabel/)
  assert.match(wxml, /detail\.simcUnitText/)
  assert.match(wxml, /detail\.briefConclusion/)
  assert.match(api, /requestSimulatorTaskDetail\(taskId\)/)
  assert.match(css, /\.task-detail-hero/)
  assert.match(css, /word-break:\s*break-all/)
  assert.match(css, /white-space:\s*pre-wrap/)
  assert.match(css, /\.build-context-box/)
  assert.doesNotMatch(css, /\.detail-code/)
})

test('task detail normalizes long build prompts into a compact report header', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const longTalentCode = `CAE${'A'.repeat(96)}`
  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-long',
    mode: 'simcraft_agent',
    question: [
      '第1轮玩家：我从职业专精页带入了冰霜法师的天赋构筑。',
      '请按大秘境多目标场景，先确认这个方案能否生成 SimC 任务。',
      `天赋导入代码：${longTalentCode}`,
      '装备候选：武器：Umbral Spire of Zuraal；饰品：Gaze of the Alnseer'
    ].join('\n'),
    request: {},
    analysis: {
      request: {
        buildContext: {
          className: '法师',
          specName: '冰霜',
          activeQueryTitle: '天赋构筑',
          details: {
            talents: { importCode: longTalentCode },
            gear: { gear: [{ slot: '武器', name: 'Umbral Spire of Zuraal' }] }
          }
        }
      },
      simulation: { ran: false, error: '' },
      recommendations: []
    }
  })

  assert.equal(normalized.heroTitle, 'SimC 任务 · 冰霜法师')
  assert.match(normalized.questionSummary, /冰霜法师的天赋构筑/)
  assert.doesNotMatch(normalized.questionSummary, new RegExp(longTalentCode))
  assert.ok(normalized.questionSummary.length < normalized.question.length)
})

test('task detail hides generated SimC preview DPS values from the report', () => {
  let pageDefinition = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('../pages/simulator/task-detail.js')]
  require('../pages/simulator/task-detail.js')
  global.Page = originalPage

  const normalized = pageDefinition.normalizeTaskDetail({
    taskId: 'task-preview',
    mode: 'simcraft_agent',
    question: '我是700装等冰法，想看大秘境 AOE DPS 是否合格',
    request: {},
    analysis: {
      request: { profileSource: 'generated' },
      simulation: {
        quality: 'preview',
        metricLabel: '正式 SimC DPS',
        metricUnit: '需要完整 /simc 导出',
        metrics: { dps: '26.129' },
        error: ''
      },
      recommendations: ['已生成可执行 SimC 模板；未执行正式 SimC DPS 模拟。']
    }
  })

  assert.equal(normalized.simcStatusText, '需完整 /simc')
  assert.equal(normalized.simcMetricLabel, '正式 SimC DPS')
  assert.equal(normalized.simcUnitText, '需要完整 /simc 导出')
  assert.equal(normalized.simcDps, '')
  assert.equal(normalized.simcDisplayValue, '未执行正式模拟')
  assert.match(normalized.briefConclusion, /未执行正式 SimC DPS 模拟/)
  assert.doesNotMatch(normalized.briefConclusion, /26\.129/)
})

test('wcl analysis page submits WCL questions through the simulator analyzer', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/simulator/wcl.js', 'utf8')
  const wxml = fs.readFileSync('pages/simulator/wcl.wxml', 'utf8')

  assert.ok(app.pages.includes('pages/simulator/wcl'))
  assert.match(js, /navTitle:\s*'分析 WCL'/)
  assert.match(wxml, /textarea[\s\S]*value="\{\{wclPrompt\}\}"/)
  assert.match(wxml, /bindtap="submitWclAnalysis"/)
  assert.match(js, /submitWclAnalysis\(\)/)
  assert.match(js, /mode:\s*'wcl'/)
  assert.match(js, /prompt:\s*this\.data\.wclPrompt/)
  assert.match(js, /saveTask:\s*true/)
  assert.match(js, /auth:\s*true/)
  assert.match(js, /allowInsecureGuestRequest:\s*true/)
})
