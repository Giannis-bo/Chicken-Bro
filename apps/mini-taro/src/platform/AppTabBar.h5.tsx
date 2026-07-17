import Taro from '@tarojs/taro'
import { useEffect, useState } from 'react'

import { TabBar } from '@wow-mini/design-system/components/TabBar'

import { isTabRoute, normalizeTabRoute, tabBarItems } from '../tab-bar-items'

function currentHashRoute(): string {
  return normalizeTabRoute(window.location.hash)
}

export function AppTabBar() {
  const [currentPath, setCurrentPath] = useState(currentHashRoute)

  useEffect(() => {
    const update = () => setCurrentPath(currentHashRoute())
    window.addEventListener('hashchange', update)
    window.addEventListener('popstate', update)
    return () => {
      window.removeEventListener('hashchange', update)
      window.removeEventListener('popstate', update)
    }
  }, [])

  if (!isTabRoute(currentPath)) return null

  const handleSelect = (pagePath: string) => {
    if (pagePath === currentPath) return
    void Taro.switchTab({ url: `/${pagePath}` })
  }

  return <TabBar currentPath={currentPath} items={tabBarItems} onSelect={handleSelect} />
}
