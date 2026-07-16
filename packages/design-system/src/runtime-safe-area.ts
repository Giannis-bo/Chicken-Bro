import Taro from '@tarojs/taro'
import type { CSSProperties } from 'react'

interface RuntimeSafeArea {
  top?: number | undefined
  bottom?: number | undefined
}

interface RuntimeWindowInfo {
  windowWidth?: number | undefined
  windowHeight?: number | undefined
  screenHeight?: number | undefined
  screenTop?: number | undefined
  statusBarHeight?: number | undefined
  safeArea?: RuntimeSafeArea | undefined
}

interface RuntimeMenuButtonRect {
  width?: number | undefined
  left?: number | undefined
  right?: number | undefined
  top?: number | undefined
  bottom?: number | undefined
}

export interface RuntimeSafeAreaMetrics {
  safeTop: number
  safeBottom: number
  capsuleSafeRight: number
  capsuleTop: number
  capsuleBottom: number
  capsuleClearanceHeight: number
}

export function safeAreaMetricsFromWindowInfo(
  windowInfo: RuntimeWindowInfo,
  menuButton: RuntimeMenuButtonRect = {},
): RuntimeSafeAreaMetrics {
  const windowWidth = Math.max(0, Number(windowInfo.windowWidth ?? 0))
  const windowHeight = Math.max(0, Number(windowInfo.windowHeight ?? 0))
  const screenHeight = Math.max(windowHeight, Number(windowInfo.screenHeight ?? windowHeight))
  const screenTop = Math.max(0, Number(windowInfo.screenTop ?? 0))
  const statusBarHeight = Math.max(0, Number(windowInfo.statusBarHeight ?? 0))
  const safeTop = Math.max(
    0,
    Math.max(statusBarHeight, Number(windowInfo.safeArea?.top ?? 0)) - screenTop,
  )
  const safeAreaBottom = Number(windowInfo.safeArea?.bottom ?? screenHeight)
  const safeBottom = Math.max(0, screenHeight - safeAreaBottom)
  const menuWidth = Math.max(0, Number(menuButton.width ?? 0))
  const menuLeft = Number(menuButton.left ?? 0)
  const menuRight = Number(menuButton.right ?? 0)
  const menuIsUsable = menuWidth > 0 && menuLeft > windowWidth / 2 && menuRight <= windowWidth + 2
  const capsuleSafeRight = menuIsUsable
    ? Math.max(0, windowWidth - menuLeft + 8)
    : 0
  const capsuleTop = menuIsUsable
    ? Math.max(0, Number(menuButton.top ?? safeTop + screenTop) - screenTop)
    : 0
  const capsuleBottom = menuIsUsable
    ? Math.max(capsuleTop, Number(menuButton.bottom ?? capsuleTop + screenTop) - screenTop)
    : 0
  const capsuleClearanceHeight = capsuleBottom > safeTop
    ? capsuleBottom - safeTop + 6
    : 0
  return {
    safeTop,
    safeBottom,
    capsuleSafeRight,
    capsuleTop,
    capsuleBottom,
    capsuleClearanceHeight,
  }
}

function isWebRuntime(): boolean {
  try {
    const environment = Taro.getEnv()
    if (environment) return environment === Taro.ENV_TYPE.WEB
  } catch {
    // Non-Taro consumers may not expose the runtime environment API.
  }
  return typeof window !== 'undefined' && typeof document !== 'undefined'
}

export function runtimeSafeAreaStyle(): CSSProperties {
  if (isWebRuntime()) return {}
  try {
    const windowInfo = typeof Taro.getWindowInfo === 'function'
      ? Taro.getWindowInfo()
      : Taro.getSystemInfoSync()
    const metrics = safeAreaMetricsFromWindowInfo(windowInfo, Taro.getMenuButtonBoundingClientRect())
    return {
      '--safe-top': `${metrics.safeTop}px`,
      '--safe-bottom': `${metrics.safeBottom}px`,
      '--capsule-safe-right': `${metrics.capsuleSafeRight}px`,
      '--capsule-top': `${metrics.capsuleTop}px`,
      '--capsule-bottom': `${metrics.capsuleBottom}px`,
      '--capsule-clearance-height': `${metrics.capsuleClearanceHeight}px`,
    } as CSSProperties
  } catch {
    return {}
  }
}
