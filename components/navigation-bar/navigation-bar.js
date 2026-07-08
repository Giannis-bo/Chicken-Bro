Component({
  options: {
    multipleSlots: true // 在组件定义时的选项中启用多slot支持
  },
  /**
   * 组件的属性列表
   */
  properties: {
    extClass: {
      type: String,
      value: ''
    },
    title: {
      type: String,
      value: ''
    },
    background: {
      type: String,
      value: ''
    },
    color: {
      type: String,
      value: ''
    },
    back: {
      type: Boolean,
      value: true
    },
    loading: {
      type: Boolean,
      value: false
    },
    homeButton: {
      type: Boolean,
      value: false,
    },
    homePath: {
      type: String,
      value: '/pages/news/news'
    },
    animated: {
      // 显示隐藏的时候opacity动画效果
      type: Boolean,
      value: true
    },
    show: {
      // 显示隐藏导航，隐藏的时候navigation-bar的高度占位还在
      type: Boolean,
      value: true,
      observer: '_showChange'
    },
    // back为true的时候，返回的页面深度
    delta: {
      type: Number,
      value: 1
    },
  },
  /**
   * 组件的初始数据
   */
  data: {
    displayStyle: ''
  },
  lifetimes: {
    attached() {
      const rect = wx.getMenuButtonBoundingClientRect()
      const systemInfo = wx.getSystemInfoSync()
      const deviceInfo = wx.getDeviceInfo ? wx.getDeviceInfo() : systemInfo
      const windowInfo = wx.getWindowInfo ? wx.getWindowInfo() : systemInfo
      const platform = deviceInfo.platform || systemInfo.platform
      const isAndroid = platform === 'android'
      const { windowWidth } = windowInfo
      const statusBarHeight = clampStatusBarHeight(
        windowInfo.statusBarHeight ??
        systemInfo.statusBarHeight ??
        deviceInfo.statusBarHeight
      )
      const rightReserve = Math.max(0, windowWidth - rect.left)
      this.setData({
        ios: !isAndroid,
        innerPaddingRight: `padding-right: ${rightReserve}px`,
        leftWidth: `width: ${rightReserve}px`,
        safeAreaTop: `--status-bar-height: ${statusBarHeight}px`
      })
    },
  },
  /**
   * 组件的方法列表
   */
  methods: {
    _showChange(show) {
      const animated = this.data.animated
      let displayStyle = ''
      if (animated) {
        displayStyle = `opacity: ${show ? '1' : '0'
          };transition:opacity 0.5s;`
      } else {
        displayStyle = `display: ${show ? '' : 'none'}`
      }
      this.setData({
        displayStyle
      })
    },
    back() {
      const data = this.data
      if (data.delta) {
        wx.navigateBack({
          delta: data.delta
        })
      }
      this.triggerEvent('back', { delta: data.delta }, {})
    },
    home() {
      wx.switchTab({
        url: this.data.homePath || '/pages/news/news'
      })
      this.triggerEvent('home', {}, {})
    }
  },
})

function clampStatusBarHeight(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number < 0) return 0
  return Math.min(number, 64)
}
