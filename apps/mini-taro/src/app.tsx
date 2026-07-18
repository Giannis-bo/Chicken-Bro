import type { PropsWithChildren } from 'react'
import { configureAssetRuntimeRoot } from '@wow-mini/assets-manifest'
import { configureRuntimeMediaRoot } from '@wow-mini/design-system/runtime-media'

import { AppTabBar } from './platform/AppTabBar'

import './app.scss'

configureAssetRuntimeRoot(__WOW_ASSET_RUNTIME_ROOT__)
configureRuntimeMediaRoot(__WOW_RUNTIME_MEDIA_ROOT__)

export default function App({ children }: PropsWithChildren) {
  return (
    <>
      {children}
      <AppTabBar />
    </>
  )
}
