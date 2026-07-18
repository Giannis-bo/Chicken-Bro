import { useDidShow } from '@tarojs/taro'

import { activeTabRouteStore } from './tab-bar-state'

export function useTabRootIdentity(pagePath: string): void {
  useDidShow(() => {
    activeTabRouteStore.set(pagePath)
  })
}
