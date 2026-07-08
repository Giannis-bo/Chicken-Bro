const { currentProfile, saveProfileDraft } = require('../common/auth-client')
const { trackPageLeave, trackPageView } = require('../common/analytics-client')
const { syncTabBarSelected } = require('../common/tabbar-sync')
const {
  buildTemplateSummary,
  deleteBuildTemplateRemote,
  fetchBuildTemplates
} = require('../common/build-template-storage')

function shortDate(value) {
  const text = String(value || '').trim()
  if (!text) return '刚刚'
  return text.includes('T') ? text.split('T')[0] : text.slice(0, 10)
}

function templateMetaChips(template) {
  const chips = []
  const fields = [
    template.className || template.classKey,
    template.specName || template.specKey,
    template.heroLabel || template.heroKey
  ]
  fields.forEach((value) => {
    const text = String(value || '').trim()
    if (text && !chips.includes(text)) chips.push(text)
  })
  return chips
}

function decorateTemplate(template) {
  const savedLabel = shortDate((template && template.updatedAt) || (template && template.createdAt))
  return {
    ...(template || {}),
    metaChips: templateMetaChips(template || {}),
    savedLabel,
    savedTimeLabel: `模板保存时间 · ${savedLabel}`
  }
}

function decorateTemplateModules() {
  return buildTemplateSummary().map((module) => ({
    ...module,
    recent: (module.recent || []).map(decorateTemplate)
  }))
}

function moduleCount(modules, type) {
  const match = (modules || []).find((item) => item && item.type === type)
  return Number(match && match.count) || 0
}

function profileStatusLabel(user) {
  return user && user.openid ? '已同步' : '本地'
}

function profileMetrics(user, modules) {
  return [
    { value: String(moduleCount(modules, 'talent')), label: '天赋模板' },
    { value: String(moduleCount(modules, 'gear')), label: '装备模板' },
    { value: profileStatusLabel(user), label: '档案状态' }
  ]
}

Page({
  data: {
    user: {
      nickname: '',
      avatarUrl: ''
    },
    nicknameDraft: '',
    savingProfile: false,
    templateModules: [],
    profileMetrics: profileMetrics({}, []),
    settings: [
      { title: '角色与服务器' },
      { title: '职业偏好' },
      { title: '数据源设置' },
      { title: '帮助与反馈' }
    ]
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    syncTabBarSelected(this, 3)
    trackPageView('pages/profile/profile', { source: 'tab' })
    this.hydrateUser()
    this.hydrateTemplates()
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/profile/profile', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onShow() {
    syncTabBarSelected(this, 3)
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/profile/profile', { source: 'tab_resume' })
    }
    this.hydrateUser()
    this.hydrateTemplates()
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/profile/profile', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  hydrateUser() {
    const user = currentProfile()
    const nickname = user.nickname || ''
    this.setData({
      user: {
        ...user,
        nickname,
        avatarUrl: user.avatarUrl || ''
      },
      nicknameDraft: nickname,
      profileMetrics: profileMetrics(user, this.data.templateModules)
    })
  },

  hydrateTemplates() {
    const templateModules = decorateTemplateModules()
    this.setData({
      templateModules,
      profileMetrics: profileMetrics(this.data.user, templateModules)
    })
    fetchBuildTemplates().then(() => {
      const nextModules = decorateTemplateModules()
      this.setData({
        templateModules: nextModules,
        profileMetrics: profileMetrics(this.data.user, nextModules)
      })
    }).catch(() => {})
  },

  onChooseAvatar(event) {
    const avatarUrl = event.detail && event.detail.avatarUrl
    if (!avatarUrl) return
    const user = { ...this.data.user, avatarUrl }
    this.setData({ user })
    this.saveUserProfile(user)
  },

  onNicknameInput(event) {
    this.setData({ nicknameDraft: event.detail.value })
  },

  saveNickname() {
    const nickname = (this.data.nicknameDraft || '').trim()
    const user = { ...this.data.user, nickname }
    this.setData({ user, nicknameDraft: nickname })
    this.saveUserProfile(user)
  },

  onNicknameConfirm() {
    this.saveNickname()
  },

  saveUserProfile(user) {
    this.setData({ savingProfile: true })
    saveProfileDraft({
      nickname: user.nickname,
      avatarUrl: user.avatarUrl
    }).then(({ payload }) => {
      if (payload) {
        this.setData({
          user: payload,
          nicknameDraft: payload.nickname || ''
        })
      }
    }).catch((error) => {
      wx.showToast({
        title: (error && (error.errMsg || error.message)) || '资料保存失败',
        icon: 'none'
      })
    }).finally(() => {
      this.setData({ savingProfile: false })
    })
  },

  deleteTemplate(event) {
    const id = event.currentTarget.dataset.id || ''
    const title = event.currentTarget.dataset.title || '这个模板'
    if (!id) return
    const remove = () => {
      deleteBuildTemplateRemote(id).finally(() => {
        this.hydrateTemplates()
      })
    }
    if (typeof wx !== 'undefined' && typeof wx.showModal === 'function') {
      wx.showModal({
        title: '删除模板',
        content: `确定删除「${title}」吗？`,
        confirmText: '删除',
        confirmColor: '#d9534f',
        success: (res) => {
          if (res && res.confirm) remove()
        }
      })
      return
    }
    remove()
  }
})
