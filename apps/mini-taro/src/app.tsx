import type { PropsWithChildren } from 'react'

import { AppTabBar } from './platform/AppTabBar'

import './app.scss'

export default function App({ children }: PropsWithChildren) {
  return (
    <>
      {children}
      <AppTabBar />
    </>
  )
}
