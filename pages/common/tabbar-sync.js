function syncTabBarSelected(page, selected) {
  if (!page || typeof page.getTabBar !== 'function') return
  const tabBar = page.getTabBar()
  if (!tabBar || typeof tabBar.setData !== 'function') return
  if (typeof tabBar.syncSelected === 'function') {
    tabBar.syncSelected()
    return
  }
  if (tabBar.data && tabBar.data.selected === selected) return
  tabBar.setData({ selected })
}

module.exports = {
  syncTabBarSelected
}
