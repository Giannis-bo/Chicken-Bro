const test = require('node:test')
const assert = require('node:assert/strict')

function resetModule(path) {
  delete require.cache[require.resolve(path)]
  return require(path)
}

test('shared api client uses the Lighthouse backend in develop and no implicit URL in release', () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => ''
  }
  let client = resetModule('../pages/common/api-client')
  assert.equal(client.apiUrl('/health'), 'http://124.223.51.33/health')

  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => ''
  }
  client = resetModule('../pages/common/api-client')
  assert.equal(client.apiUrl('/health'), '')
})

test('builds api returns fallback without an API base and remote payload when request succeeds', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without an api base url')
    }
  }
  let api = resetModule('../pages/builds/builds-api')
  let result = await api.requestBuildsHome()
  assert.equal(result.fromFallback, true)
  assert.equal(result.payload.navTitle, '职业专精')

  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: ({ success }) => success({ statusCode: 200, data: { navTitle: '远端职业专精', quickActions: [] } })
  }
  api = resetModule('../pages/builds/builds-api')
  result = await api.requestBuildsHome()
  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.navTitle, '远端职业专精')
})

test('pve and simulator apis expose fallback payloads', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without an api base url')
    }
  }
  const pveApi = resetModule('../pages/pve/pve-api')
  const simulatorApi = resetModule('../pages/simulator/simulator-api')

  const pveHome = await pveApi.requestPveHome()
  const simulatorHome = await simulatorApi.requestSimulatorHome()
  const analysis = await simulatorApi.requestSimulatorAnalysis({ mode: 'simcraft' })

  assert.equal(pveHome.fromFallback, true)
  assert.equal(pveHome.payload.navTitle, '副本')
  assert.equal(simulatorHome.fromFallback, true)
  assert.equal(simulatorHome.payload.navTitle, '智能分析')
  assert.deepEqual(
    simulatorHome.payload.analysisModules.map((module) => module.title),
    ['模拟 SimC', '分析 WCL', '任务列表']
  )
  assert.equal(simulatorHome.payload.metrics, undefined)
  assert.equal(analysis.fromFallback, true)
  assert.equal(analysis.payload.mode, 'simcraft')
})

test('simulator analysis posts prompt to backend without requiring authenticated https', async () => {
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft',
          status: 'ready',
          request: {
            prompt: '帮我跑一下冰法单体',
            runSimulation: true
          },
          simulation: {
            ran: true,
            summary: 'DPS Ranking: 123456'
          },
          recommendations: ['本次 SimC 已跑通，当前 profile 约为 123456 DPS。']
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorAnalysis({
    mode: 'simcraft',
    prompt: '帮我跑一下冰法单体',
    runSimulation: true
  })

  assert.equal(result.fromFallback, false)
  assert.match(captured.url, /\/api\/simulator\/analyze$/)
  assert.equal(captured.method, 'POST')
  assert.equal(captured.data.prompt, '帮我跑一下冰法单体')
  assert.equal(captured.data.runSimulation, true)
  assert.equal(captured.header.Authorization, undefined)
  assert.equal(result.payload.simulation.ran, true)
})

test('simulator analysis allows enough time for real SimC and LLM results', async () => {
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft',
          status: 'ready',
          simulation: {
            ran: true,
            metrics: { dps: '238.715' }
          },
          recommendations: ['本次 SimC 已跑通，当前 profile 约为 238.715 DPS。']
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  await simulatorApi.requestSimulatorAnalysis({
    mode: 'simcraft',
    prompt: '帮我跑一下真实 profile',
    runSimulation: true
  })

  assert.ok(captured.timeout >= 60000)
})

test('simulator analysis can opt into authenticated task storage', async () => {
  let captured = null
  global.getApp = () => ({ globalData: { backendApiBaseUrl: 'https://wow.example.test' } })
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => key === 'wow_backend_auth_token' ? 'token-for-task' : '',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft_agent',
          status: 'ready',
          recommendations: [],
          taskId: 'task-1'
        }
      })
    }
  }
  const simulatorApi = resetModule('../pages/simulator/simulator-api')

  const result = await simulatorApi.requestSimulatorAnalysis(
    { mode: 'simcraft_agent', prompt: '已确认的需求' },
    { auth: true }
  )

  assert.equal(result.payload.taskId, 'task-1')
  assert.match(captured.url, /^https:\/\/wow\.example\.test\/api\/simulator\/analyze$/)
  assert.equal(captured.header.Authorization, 'Bearer token-for-task')
  delete global.getApp
})

test('simulator analysis confirm-only requests do not require auth', async () => {
  let captured = null
  delete global.getApp
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => 'token-that-should-not-be-used',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft_agent',
          status: 'ready',
          recommendations: []
        }
      })
    }
  }
  const simulatorApi = resetModule('../pages/simulator/simulator-api')

  await simulatorApi.requestSimulatorAnalysis(
    { mode: 'simcraft_agent', prompt: '澄清中', confirmOnly: true }
  )

  assert.equal(captured.header.Authorization, undefined)
})

test('simulator agent fails closed when older backend returns empty profile', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: (options) => {
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft_agent',
          status: 'ready',
          request: {
            prompt: '我是现在是290装等的风暴元素萨，帮我看看理想的5目标AOE模拟多少伤害？',
            runSimulation: true
          },
          stages: [
            { key: 'profile_check', title: 'Profile 检查', status: 'blocked', executor: 'backend', summary: '缺少完整 SimCraft profile' },
            { key: 'simc_execution', title: 'SimC 执行', status: 'failed', executor: 'simcraft', summary: 'empty profile', metric: '' }
          ],
          simulation: {
            ran: false,
            error: 'empty profile'
          },
          recommendations: ['旧后端错误地尝试执行空 profile。']
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorAnalysis({
    mode: 'simcraft_agent',
    message: '我是现在是290装等的风暴元素萨，帮我看看理想的5目标AOE模拟多少伤害？',
    prompt: '我是现在是290装等的风暴元素萨，帮我看看理想的5目标AOE模拟多少伤害？',
    round: 1,
    runSimulation: true
  })

  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.agent.status, 'confirmation_failed')
  assert.equal(result.payload.agent.intent, 'baseline')
  assert.deepEqual(result.payload.agent.missingSlots, [])
  assert.doesNotMatch(result.payload.agent.question, /\/simc|角色名|服务器/)
  assert.equal(result.payload.stages[0].status, 'failed')
  assert.equal(result.payload.stages[1].status, 'skipped')
  assert.equal(result.payload.simulation.error, 'legacy backend response missing agent')
  assert.match(result.payload.recommendations[0], /重试/)
})

test('simulator agent fails closed when older backend omits agent payload', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: () => '',
    request: (options) => {
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft_agent',
          status: 'ready',
          request: {
            prompt: '第1轮玩家：我现在290风暴元素萨，大秘境 AOE DPS 多少合格？',
            runSimulation: false
          },
          simulation: {
            ran: false,
            error: 'missing simcraft profile'
          },
          recommendations: ['未执行 SimC。']
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorAnalysis({
    mode: 'simcraft_agent',
    message: '第1轮玩家：我现在290风暴元素萨，大秘境 AOE DPS 多少合格？',
    prompt: '第1轮玩家：我现在290风暴元素萨，大秘境 AOE DPS 多少合格？',
    round: 1,
    confirmOnly: true
  })

  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.agent.status, 'confirmation_failed')
  assert.doesNotMatch(result.payload.agent.question, /\/simc|角色名|服务器/)
  assert.match(result.payload.agent.question, /重试/)
  assert.equal(result.payload.request.runSimulation, false)
})

test('simulator fallback fails closed without local semantic quick replies', async () => {
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: () => '',
    request: () => {
      throw new Error('request should not run without an api base url')
    }
  }
  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorAnalysis({
    mode: 'simcraft_agent',
    message: '我285的术士，大秘境啥DPS合格？',
    prompt: '我285的术士，大秘境啥DPS合格？',
    round: 1,
    confirmOnly: true
  })

  assert.equal(result.fromFallback, true)
  assert.equal(result.payload.agent.status, 'confirmation_failed')
  assert.deepEqual(result.payload.agent.quickReplies, [])
  assert.match(result.payload.agent.question, /重试/)
  assert.doesNotMatch(JSON.stringify(result.payload), /冰法|元素萨|恶魔术|惩戒/)
})

test('auth client exchanges wx.login code and stores backend token', async () => {
  const storage = {}
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    login: ({ success }) => success({ code: 'wx-code-1' }),
    request: ({ url, method, data, success }) => {
      assert.match(url, /\/api\/auth\/wechat-login$/)
      assert.equal(method, 'POST')
      assert.equal(data.code, 'wx-code-1')
      success({
        statusCode: 200,
        data: {
          accessToken: 'token-1',
          tokenType: 'Bearer',
          user: { openid: 'openid-1', nickname: '', avatarUrl: '' }
        }
      })
    }
  }

  const auth = resetModule('../pages/common/auth-client')
  const result = await auth.loginWithWechat()

  assert.equal(result.accessToken, 'token-1')
  assert.equal(auth.currentAuth().accessToken, 'token-1')
  assert.equal(auth.currentAuth().user.openid, 'openid-1')
})

test('authorized requests attach bearer token from storage', async () => {
  const storage = {
    wow_backend_api_base_url: 'https://api.example.test',
    wow_backend_auth_token: 'token-2'
  }
  let authorization = ''
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: ({ header, success }) => {
      authorization = header.Authorization
      success({ statusCode: 200, data: { ok: true } })
    }
  }

  const client = resetModule('../pages/common/api-client')
  const result = await client.requestJson('/api/private', {
    auth: true,
    fallback: () => ({ ok: false })
  })

  assert.equal(result.fromFallback, false)
  assert.equal(authorization, 'Bearer token-2')
})

test('shared api client attaches anonymous analytics headers to backend requests', async () => {
  const storage = {
    wow_backend_api_base_url: 'https://api.example.test'
  }
  let headers = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    request: ({ header, success }) => {
      headers = header
      success({ statusCode: 200, data: { ok: true } })
    }
  }

  const client = resetModule('../pages/common/api-client')
  await client.requestJson('/health', {
    fallback: () => ({ ok: false })
  })

  assert.match(headers['X-Wow-Client-Id'], /^mp-/)
  assert.match(headers['X-Wow-Session-Id'], /^session-/)
  assert.equal(headers['X-Wow-Platform'], 'miniprogram')
  assert.equal(storage.wow_analytics_client_id, headers['X-Wow-Client-Id'])
})

test('authorized requests do not send bearer token over insecure http base url', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-3'
  }
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: () => {
      throw new Error('authenticated request should not run over http')
    }
  }

  const client = resetModule('../pages/common/api-client')
  const result = await client.requestJson('/api/private', {
    auth: true,
    fallback: () => ({ ok: false })
  })

  assert.equal(result.fromFallback, true)
  assert.match(result.error, /insecure api base url/)
})

test('simulator task submit can use insecure http as guest without sending bearer token', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-that-must-stay-local'
  }
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          mode: 'simcraft_agent',
          status: 'ready',
          recommendations: ['任务已保存'],
          taskId: 'guest-task-1'
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorAnalysis(
    { mode: 'simcraft_agent', prompt: '已确认的需求', saveTask: true },
    { auth: true, allowInsecureGuestRequest: true }
  )

  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.taskId, 'guest-task-1')
  assert.match(captured.url, /^http:\/\/api\.example\.test\/api\/simulator\/analyze$/)
  assert.equal(captured.header.Authorization, undefined)
  assert.equal(captured.data.saveTask, true)
  assert.match(captured.data.guestId, /^guest-/)
  assert.equal(storage.wow_simulator_guest_id, captured.data.guestId)
})

test('simulator task list can read guest tasks over insecure http without bearer token', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-that-must-stay-local',
    wow_simulator_guest_id: 'guest-device-a'
  }
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          user: { openid: 'guest-simulator' },
          tasks: [{ taskId: 'guest-task-1', mode: 'simcraft_agent' }]
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorTasks()

  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.tasks[0].taskId, 'guest-task-1')
  assert.match(captured.url, /^http:\/\/api\.example\.test\/api\/simulator\/tasks\?guest=1&guestId=guest-device-a$/)
  assert.equal(captured.header.Authorization, undefined)
})

test('simulator task detail can read a saved guest task over insecure http', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-that-must-stay-local',
    wow_simulator_guest_id: 'guest-device-a'
  }
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    request: (options) => {
      captured = options
      options.success({
        statusCode: 200,
        data: {
          task: {
            taskId: 'guest-task-1',
            question: '第1轮玩家：290元素萨大秘境AOE',
            request: { prompt: '第1轮玩家：290元素萨大秘境AOE' },
            analysis: {
              recommendations: ['本次 SimC 已跑通。'],
              agent: { draftProfile: 'shaman="Generated_Elemental_Shaman"' },
              simulation: { ran: true, summary: 'DPS Ranking: 123456' }
            }
          }
        }
      })
    }
  }

  const simulatorApi = resetModule('../pages/simulator/simulator-api')
  const result = await simulatorApi.requestSimulatorTaskDetail('guest-task-1')

  assert.equal(result.fromFallback, false)
  assert.equal(result.payload.task.taskId, 'guest-task-1')
  assert.match(captured.url, /^http:\/\/api\.example\.test\/api\/simulator\/task\?id=guest-task-1&guest=1&guestId=guest-device-a$/)
  assert.equal(captured.header.Authorization, undefined)
})

test('analytics client posts batches with bearer only on https', async () => {
  const storage = {
    wow_backend_api_base_url: 'https://api.example.test',
    wow_backend_auth_token: 'token-analytics'
  }
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    request: (options) => {
      captured = options
      options.success({ statusCode: 200, data: { ok: true } })
    }
  }
  global.getCurrentPages = () => [{ route: 'pages/news/news' }]

  resetModule('../pages/common/api-client')
  const analytics = resetModule('../pages/common/analytics-client')
  const ok = await analytics.trackEvent('news_home_view', { source: 'tab' })

  assert.equal(ok, true)
  assert.match(captured.url, /^https:\/\/api\.example\.test\/api\/analytics\/events$/)
  assert.equal(captured.method, 'POST')
  assert.equal(captured.header.Authorization, 'Bearer token-analytics')
  assert.match(captured.header['X-Wow-Client-Id'], /^mp-/)
  assert.equal(captured.data.events[0].eventName, 'news_home_view')
  assert.equal(JSON.parse(storage.wow_analytics_event_queue).length, 0)
  delete global.getCurrentPages
})

test('analytics client keeps bearer token local for insecure http analytics posts', async () => {
  const storage = {
    wow_backend_api_base_url: 'http://api.example.test',
    wow_backend_auth_token: 'token-analytics'
  }
  let captured = null
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    request: (options) => {
      captured = options
      options.success({ statusCode: 200, data: { ok: true } })
    }
  }

  resetModule('../pages/common/api-client')
  const analytics = resetModule('../pages/common/analytics-client')
  await analytics.trackEvent('pve_home_view', { source: 'tab' })

  assert.match(captured.url, /^http:\/\/api\.example\.test\/api\/analytics\/events$/)
  assert.equal(captured.header.Authorization, undefined)
})

test('analytics client stores at most 200 offline events', async () => {
  const storage = {}
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'release' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    request: () => {
      throw new Error('request should not run without api base url')
    }
  }

  resetModule('../pages/common/api-client')
  const analytics = resetModule('../pages/common/analytics-client')
  for (let index = 0; index < 205; index += 1) {
    await analytics.trackEvent('page_view', { index }, { page: 'pages/news/news' })
  }

  const queue = JSON.parse(storage.wow_analytics_event_queue)
  assert.equal(queue.length, 200)
  assert.equal(queue[0].properties.index, 5)
})

test('profile drafts persist locally even when remote auth endpoint is unavailable', async () => {
  const storage = {}
  global.wx = {
    getAccountInfoSync: () => ({ miniProgram: { envVersion: 'develop' } }),
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value
    },
    login: ({ success }) => success({ code: 'wx-code-404' }),
    request: ({ success }) => success({ statusCode: 404, data: { error: 'not_found' } })
  }

  const auth = resetModule('../pages/common/auth-client')
  const result = await auth.saveProfileDraft({
    nickname: '微信昵称',
    avatarUrl: 'wxfile://avatar'
  })

  assert.equal(result.fromFallback, true)
  assert.equal(auth.currentProfile().nickname, '微信昵称')
  assert.equal(auth.currentProfile().avatarUrl, 'wxfile://avatar')
})
