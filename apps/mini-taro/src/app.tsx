import Taro from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, type PropsWithChildren } from 'react'

import { AppTabBar } from './platform/AppTabBar'
import WebApp from './web/WebApp'

import './app.scss'

function isWebRuntime(): boolean {
  try {
    return Taro.getEnv() === Taro.ENV_TYPE.WEB
  } catch {
    return false
  }
}

export default function App({ children }: PropsWithChildren) {
  const webRuntime = isWebRuntime()

  useEffect(() => {
    if (!webRuntime || typeof document === 'undefined' || !document.body) return undefined

    document.documentElement.classList.add('web-runtime-scroll')
    document.body.classList.add('web-runtime-scroll')
    return () => {
      document.documentElement.classList.remove('web-runtime-scroll')
      document.body.classList.remove('web-runtime-scroll')
    }
  }, [webRuntime])

  if (webRuntime) {
    return (
      <>
        <WebApp />
        <View className="web-page-mount">{children}</View>
      </>
    )
  }

  return (
    <>
      {children}
      <AppTabBar />
    </>
  )
}
