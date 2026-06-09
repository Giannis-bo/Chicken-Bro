const { currentProfile, saveProfileDraft } = require('../common/auth-client')

Page({
  data: {
    user: {
      nickname: '',
      avatarUrl: ''
    },
    nicknameDraft: '',
    savingProfile: false,
    metrics: [
      { value: '4', label: '收藏职业' },
      { value: '2', label: '关注角色' },
      { value: '12', label: '订阅词条' }
    ],
    abilities: [
      { name: '资讯订阅', desc: '关注正式服、测试服、玩法与职业强度变化。', level: '已开启' },
      { name: '职业专精 BD', desc: '收藏天赋搭配、毕业装备和常用构筑。', level: '已开启' },
      { name: '大秘境与团本', desc: '追踪榜单阵容、玩家数据和副本热点。', level: '已开启' },
      { name: '构筑模拟器', desc: '用 AI 辅助 SimCraft 与 WCL 数据分析。', level: '已开启' }
    ],
    settings: [
      { title: '角色与服务器' },
      { title: '职业偏好' },
      { title: '数据源设置' },
      { title: '帮助与反馈' }
    ]
  },

  onLoad() {
    this.hydrateUser()
  },

  onShow() {
    this.hydrateUser()
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
      nicknameDraft: nickname
    })
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
  }
})
