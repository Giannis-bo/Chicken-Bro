import Taro from '@tarojs/taro'
import type { PropsWithChildren } from 'react'
import { configureAssetRuntimeRoot } from '@wow-mini/assets-manifest'
import { configureRuntimeMediaRoot } from '@wow-mini/design-system/runtime-media'

import { AppTabBar } from './platform/AppTabBar'
import WebApp from './web/WebApp'

import './app.scss'

configureAssetRuntimeRoot(__WOW_ASSET_RUNTIME_ROOT__)
configureRuntimeMediaRoot(__WOW_RUNTIME_MEDIA_ROOT__)

function isWebRuntime(): boolean {
  try {
    return Taro.getEnv() === Taro.ENV_TYPE.WEB
  } catch {
    return false
  }
}

export default function App({ children }: PropsWithChildren) {
  if (isWebRuntime()) return <WebApp />

  return (
    <>
      {children}
      <AppTabBar />
    </>
  )
}
