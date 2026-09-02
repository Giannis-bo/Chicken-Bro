import Taro from '@tarojs/taro'
import { useEffect, useState } from 'react'

import { CoreTabBar } from '../components/CoreTabBar'
import {
  resolveActiveTabRoute,
  tabBarItems,
} from '../tab-bar-items'
import { activeTabRouteStore } from '../tab-bar-state'

function activePath(): string {
  const pages = Taro.getCurrentPages()
  return resolveActiveTabRoute([
    pages.at(-1)?.route,
    Taro.getCurrentInstance().router?.path,
  ])
}

export default function CustomTabBar() {
  const [currentPath, setCurrentPath] = useState(() => activeTabRouteStore.get() ?? activePath())

  useEffect(() => {
    return activeTabRouteStore.subscribe(setCurrentPath)
  }, [])

  const handleSelect = (pagePath: string) => {
    if (pagePath === currentPath) return

    const previousPath = currentPath
    activeTabRouteStore.set(pagePath)
    void Taro.switchTab({ url: `/${pagePath}` }).catch(() => {
      activeTabRouteStore.set(resolveActiveTabRoute([activePath()], previousPath))
    })
  }

  return (
    <CoreTabBar
      currentPath={currentPath}
      items={tabBarItems}
      onSelect={handleSelect}
    />
  )
}
