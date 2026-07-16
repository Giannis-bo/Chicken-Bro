import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/taro', () => ({
  default: {
    ENV_TYPE: { WEB: 'WEB' },
    getEnv: vi.fn(() => 'WEB'),
  },
}))

import { safeAreaMetricsFromWindowInfo } from './runtime-safe-area'

describe('runtime safe-area metrics', () => {
  it('uses screen coordinates for native iPhone top and home-indicator insets', () => {
    expect(safeAreaMetricsFromWindowInfo({
      windowWidth: 390,
      windowHeight: 844,
      screenHeight: 844,
      statusBarHeight: 47,
      safeArea: { top: 47, bottom: 810 },
    }, {
      width: 87,
      left: 295,
      right: 382,
      top: 51,
      bottom: 83,
    })).toEqual({
      safeTop: 47,
      safeBottom: 34,
      capsuleSafeRight: 103,
      capsuleTop: 51,
      capsuleBottom: 83,
      capsuleClearanceHeight: 42,
    })
  })

  it('does not invent an inset when the platform reports a full safe area', () => {
    expect(safeAreaMetricsFromWindowInfo({
      windowWidth: 390,
      windowHeight: 844,
      screenHeight: 844,
      statusBarHeight: 0,
      safeArea: { top: 0, bottom: 844 },
    })).toEqual({
      safeTop: 0,
      safeBottom: 0,
      capsuleSafeRight: 0,
      capsuleTop: 0,
      capsuleBottom: 0,
      capsuleClearanceHeight: 0,
    })
  })

  it('converts a screen-coordinate safe bottom into the current window coordinate space', () => {
    expect(safeAreaMetricsFromWindowInfo({
      windowWidth: 390,
      windowHeight: 797,
      screenHeight: 844,
      screenTop: 47,
      statusBarHeight: 47,
      safeArea: { top: 47, bottom: 810 },
    })).toEqual({
      safeTop: 0,
      safeBottom: 34,
      capsuleSafeRight: 0,
      capsuleTop: 0,
      capsuleBottom: 0,
      capsuleClearanceHeight: 0,
    })
  })
})
