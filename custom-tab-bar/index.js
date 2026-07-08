const TAB_LIST = [
  {
    pagePath: '/pages/news/news',
    text: '最新资讯',
    glyph: '讯',
    iconPath: '/assets/tabbar/news.png',
    selectedIconPath: '/assets/tabbar/news-selected.png'
  },
  {
    pagePath: '/pages/builds/builds',
    text: '职业专精',
    glyph: '专',
    iconPath: '/assets/tabbar/builds.png',
    selectedIconPath: '/assets/tabbar/builds-selected.png'
  },
  {
    pagePath: '/pages/simulator/simulator',
    text: '智能分析',
    glyph: '析',
    iconPath: '/assets/tabbar/simulator.png',
    selectedIconPath: '/assets/tabbar/simulator-selected.png'
  },
  {
    pagePath: '/pages/profile/profile',
    text: '我的',
    glyph: '我',
    iconPath: '/assets/tabbar/profile.png',
    selectedIconPath: '/assets/tabbar/profile-selected.png'
  }
]

function normalizeRoute(route) {
  const text = String(route || '').trim()
  return text.startsWith('/') ? text : `/${text}`
}

function selectedIndexForRoute(route) {
  const current = normalizeRoute(route)
  const index = TAB_LIST.findIndex((item) => normalizeRoute(item.pagePath) === current)
  return index >= 0 ? index : 0
}

function emptyIconFailures() {
  return TAB_LIST.map(() => false)
}

function tabListForSelected(selected, iconFailures) {
  const failures = Array.isArray(iconFailures) ? iconFailures : emptyIconFailures()
  return TAB_LIST.map((item, index) => {
    const active = selected === index
    return {
      ...item,
      itemClass: active ? 'is-selected' : '',
      currentIconPath: active ? item.selectedIconPath : item.iconPath,
      iconLoadFailed: !!failures[index]
    }
  })
}

Component({
  data: {
    selected: 0,
    iconFailures: emptyIconFailures(),
    list: tabListForSelected(0, emptyIconFailures())
  },
  methods: {
    syncSelected() {
      const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
      const current = pages && pages.length ? pages[pages.length - 1] : null
      const selected = selectedIndexForRoute(current && current.route)
      const iconFailures = emptyIconFailures()
      if (this.data && this.data.selected === selected) {
        this.setData({ iconFailures, list: tabListForSelected(selected, iconFailures) })
        return
      }
      this.setData({ selected, iconFailures, list: tabListForSelected(selected, iconFailures) })
    },
    handleIconError(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      const index = Number(dataset.index)
      if (!Number.isInteger(index) || index < 0 || index >= TAB_LIST.length) return
      const iconFailures = (this.data.iconFailures || emptyIconFailures()).slice()
      iconFailures[index] = true
      this.setData({
        iconFailures,
        list: tabListForSelected(this.data.selected || 0, iconFailures)
      })
    },
    switchTab(event) {
      const path = event.currentTarget && event.currentTarget.dataset
        ? event.currentTarget.dataset.path
        : ''
      if (!path) return
      wx.switchTab({ url: path })
    }
  },
  lifetimes: {
    attached() {
      this.syncSelected()
    }
  },
  pageLifetimes: {
    show() {
      this.syncSelected()
    }
  }
})
