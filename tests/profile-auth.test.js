const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function loadProfilePageConfig(stubs = {}) {
  let pageConfig = null
  const originalPage = global.Page
  global.Page = (definition) => {
    pageConfig = definition
  }
  const previousCache = new Map()
  Object.entries(stubs).forEach(([modulePath, exports]) => {
    const resolved = require.resolve(modulePath)
    previousCache.set(resolved, require.cache[resolved])
    require.cache[resolved] = {
      id: resolved,
      filename: resolved,
      loaded: true,
      exports
    }
  })
  try {
    delete require.cache[require.resolve('../pages/profile/profile.js')]
    require('../pages/profile/profile.js')
  } finally {
    global.Page = originalPage
    Object.keys(stubs).forEach((modulePath) => {
      const resolved = require.resolve(modulePath)
      const previous = previousCache.get(resolved)
      if (previous) {
        require.cache[resolved] = previous
      } else {
        delete require.cache[resolved]
      }
    })
  }
  return pageConfig
}

function createProfileInstance(pageConfig) {
  return {
    ...pageConfig,
    data: { ...(pageConfig.data || {}) },
    setData(update) {
      this.data = { ...this.data, ...(update || {}) }
    }
  }
}

test('profile page exposes WeChat avatar and nickname profile bindings', () => {
  const js = fs.readFileSync('pages/profile/profile.js', 'utf8')
  const wxml = fs.readFileSync('pages/profile/profile.wxml', 'utf8')

  assert.match(js, /saveProfile/)
  assert.match(js, /saveProfileDraft/)
  assert.match(js, /onChooseAvatar/)
  assert.match(js, /onNicknameInput/)
  assert.match(js, /onNicknameConfirm/)
  assert.match(wxml, /open-type="chooseAvatar"/)
  assert.match(wxml, /bindchooseavatar="onChooseAvatar"/)
  assert.match(wxml, /bindinput="onNicknameInput"/)
  assert.match(wxml, /bindconfirm="onNicknameConfirm"/)
  assert.match(wxml, /placeholder="点击填写微信昵称"/)
})

test('profile page replaces abilities with talent and gear template modules', () => {
  const js = fs.readFileSync('pages/profile/profile.js', 'utf8')
  const wxml = fs.readFileSync('pages/profile/profile.wxml', 'utf8')
  const css = fs.readFileSync('pages/profile/profile.wxss', 'utf8')

  assert.doesNotMatch(js, /abilities:\s*\[/)
  assert.doesNotMatch(wxml, /我的能力/)
  assert.match(js, /buildTemplateSummary/)
  assert.match(js, /deleteBuildTemplateRemote/)
  assert.match(js, /fetchBuildTemplates/)
  assert.match(js, /hydrateTemplates\(\)/)
  assert.match(wxml, /天赋模板/)
  assert.match(wxml, /装备模板/)
  assert.match(wxml, /templateModules/)
  assert.match(wxml, /profileMetrics/)
  assert.match(wxml, /profile-cockpit-content[\s\S]*profile-identity-row[\s\S]*profile-signal-strip/)
  const cockpitStart = wxml.indexOf('<view class="profile-cockpit">')
  const cockpitEnd = wxml.indexOf('\n\n      <view class="section">', cockpitStart)
  const signalIndex = wxml.indexOf('<view class="profile-signal-strip">')
  assert.ok(signalIndex > cockpitStart && signalIndex < cockpitEnd)
  assert.doesNotMatch(wxml, /assets\/generated/)
  assert.match(wxml, /item\.count/)
  assert.match(wxml, /item\.recent/)
  assert.match(wxml, /template-meta-chip/)
  assert.match(wxml, /bindtap="deleteTemplate"/)
  assert.match(wxml, /data-id="\{\{template\.id\}\}"/)
  assert.match(wxml, /template\.savedTimeLabel/)
  assert.doesNotMatch(wxml, /template\.source\}\} · \{\{template\.savedLabel/)
  assert.doesNotMatch(js, /收藏职业|关注角色|订阅词条/)
  assert.doesNotMatch(wxml, /收藏职业|关注角色|订阅词条/)
  assert.match(js, /profileMetrics\(user, modules\)/)
  assert.match(css, /\.template-module/)
  assert.match(css, /\.template-delete-button/)
  assert.match(css, /\.template-delete-button\s*\{[^}]*width:\s*72rpx/s)
  assert.match(css, /\.profile-cockpit/)
  assert.match(css, /\.profile-cockpit-content\s*\{[^}]*display:\s*grid/s)
  assert.match(css, /\.profile-identity-row\s*\{[^}]*grid-template-columns:\s*92rpx minmax\(0, 1fr\)/s)
  assert.match(css, /\.profile-signal-strip/)
})

test('profile template cards show only class spec hero chips and saved time for talent and gear', () => {
  const pageConfig = loadProfilePageConfig({
    '../pages/common/auth-client.js': {
      currentProfile: () => ({}),
      saveProfileDraft: () => Promise.resolve({ payload: null })
    },
    '../pages/common/analytics-client.js': {
      trackPageLeave: () => {},
      trackPageView: () => {}
    },
    '../pages/common/build-template-storage.js': {
      buildTemplateSummary: () => ([
        {
          type: 'talent',
          count: 1,
          recent: [{
            id: 'talent-1',
            title: '法师-冰霜-法术投射者-0620 2132',
            className: '法师',
            specName: '冰霜',
            heroLabel: '法术投射者',
            scenarioTitle: '单体',
            statusLabel: '已保存',
            source: 'Raider.IO',
            updatedAt: '2026-06-20T21:32:00Z'
          }]
        },
        {
          type: 'gear',
          count: 1,
          recent: [{
            id: 'gear-1',
            title: '萨满祭司-元素-单体-0626 2231',
            className: '萨满祭司',
            specName: '元素',
            heroLabel: '风暴使者',
            scenarioTitle: '单体',
            statusLabel: '完整配置',
            source: '装备模拟器',
            createdAt: '2026-06-26T22:31:00Z'
          }]
        }
      ]),
      deleteBuildTemplateRemote: () => Promise.resolve(),
      fetchBuildTemplates: () => Promise.resolve()
    }
  })
  const page = createProfileInstance(pageConfig)

  page.hydrateTemplates()

  const [talentModule, gearModule] = page.data.templateModules
  assert.deepEqual(talentModule.recent[0].metaChips, ['法师', '冰霜', '法术投射者'])
  assert.equal(talentModule.recent[0].savedTimeLabel, '模板保存时间 · 2026-06-20')
  assert.deepEqual(gearModule.recent[0].metaChips, ['萨满祭司', '元素', '风暴使者'])
  assert.equal(gearModule.recent[0].savedTimeLabel, '模板保存时间 · 2026-06-26')
})
