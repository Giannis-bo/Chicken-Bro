import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { TabBar } from '@wow-mini/design-system'

import { tabBarItems } from '../tab-bar-items'

function activePath(): string {
  return Taro.getCurrentInstance().router?.path ?? tabBarItems[0]?.pagePath ?? 'pages/news/news'
}

export default function CustomTabBar() {
  const [currentPath, setCurrentPath] = useState(activePath)

  useDidShow(() => setCurrentPath(activePath()))

  const handleSelect = (pagePath: string) => {
    if (pagePath === currentPath.replace(/^\//, '')) return
    void Taro.switchTab({ url: `/${pagePath}` })
  }

  return (
    <TabBar
      currentPath={currentPath}
      items={tabBarItems}
      onSelect={handleSelect}
    />
  )
}
