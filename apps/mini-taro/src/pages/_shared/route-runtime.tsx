import Taro from '@tarojs/taro'
import { Text, View } from '@tarojs/components'
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ApiResult } from '@wow-mini/api-client'
import { ActionButton } from '@wow-mini/design-system/components/ActionButton'
import { ChannelDock } from '@wow-mini/design-system/components/ChannelDock'
import { FeaturedCarousel } from '@wow-mini/design-system/components/FeaturedCarousel'
import { RankedFeed } from '@wow-mini/design-system/components/RankedFeed'
import { StatusVisual } from '@wow-mini/design-system/components/StatusVisual'
import { WowPanel } from '@wow-mini/design-system/components/WowPanel'
import type { RouteDataState } from '@wow-mini/domain'

import styles from './routes.module.scss'

export type FallbackPolicy = 'blocked' | 'stale'

const TAB_ROUTES = new Set([
  '/pages/news/news',
  '/pages/builds/builds',
  '/pages/simulator/simulator',
  '/pages/profile/profile',
])

export interface AsyncRouteOptions<T> {
  fallbackPolicy?: FallbackPolicy
  isEmpty?: (value: T) => boolean
}

export interface AsyncRoute<T> {
  state: RouteDataState<T>
  data: T | undefined
  load: () => Promise<void>
}

function dataFromState<T>(state: RouteDataState<T>): T | undefined {
  if ('data' in state) return state.data
  if ('previous' in state) return state.previous
  return undefined
}

export function useAsyncRoute<T>(
  request: () => Promise<ApiResult<T>>,
  options: AsyncRouteOptions<T> = {},
): AsyncRoute<T> {
  const requestRef = useRef(request)
  const optionsRef = useRef(options)
  const serialRef = useRef(0)
  const mountedRef = useRef(true)
  const [state, setState] = useState<RouteDataState<T>>({
    state: 'loading',
    trust: { level: 'unknown', reason: '首次加载' },
  })

  requestRef.current = request
  optionsRef.current = options

  useEffect(() => () => {
    mountedRef.current = false
    serialRef.current += 1
  }, [])

  const load = useCallback(async () => {
    const serial = ++serialRef.current
    setState((current) => {
      const previous = dataFromState(current)
      return {
        state: 'loading',
        trust: { level: 'unknown', reason: '正在请求后端' },
        ...(previous === undefined ? {} : { previous }),
      }
    })
    try {
      const result = await requestRef.current()
      if (!mountedRef.current || serial !== serialRef.current) return
      const currentOptions = optionsRef.current
      if (result.fromFallback) {
        const reason = result.error || '后端数据不可用'
        if (currentOptions.fallbackPolicy === 'stale') {
          setState({
            state: 'stale',
            data: result.payload,
            staleReason: reason,
            trust: { level: 'unknown', reason },
          })
        } else {
          setState({
            state: 'blocked',
            reason,
            trust: { level: 'blocked', reason },
          })
        }
        return
      }
      if (currentOptions.isEmpty?.(result.payload)) {
        setState({ state: 'empty', trust: { level: 'backend_verified' } })
        return
      }
      setState({ state: 'ready', data: result.payload, trust: { level: 'backend_verified' } })
    } catch (error) {
      if (!mountedRef.current || serial !== serialRef.current) return
      setState((current) => {
        const previous = dataFromState(current)
        return {
          state: 'error',
          error: error instanceof Error ? error.message : 'request failed',
          trust: { level: 'unknown', reason: '请求异常' },
          ...(previous === undefined ? {} : { previous }),
        }
      })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { state, data: dataFromState(state), load }
}

export interface RouteStatePanelProps {
  state: RouteDataState<unknown>
  loadingText?: string
  emptyText?: string
  onRetry?: () => void
  loadingLayout?: 'panel' | 'news-home' | undefined
}

export function RouteStatePanel({
  state,
  loadingText = '正在加载',
  emptyText = '暂无内容',
  onRetry,
  loadingLayout = 'panel',
}: RouteStatePanelProps) {
  if (state.state === 'ready' || state.state === 'stale' || state.state === 'partial' || state.state === 'source_reference') {
    return (
      <View
        className={styles['routeStateMarker'] ?? ''}
        data-route-state={state.state}
      />
    )
  }
  if (state.state === 'loading' && loadingLayout === 'news-home') {
    return (
      <View
        className={styles['newsLoading'] ?? ''}
        data-loading-layout="news-home"
        data-route-state="loading"
      >
        <WowPanel description={loadingText} title="今日资讯概览" variant="cockpit">
          <StatusVisual
            compact
            glyph="row"
            label="正在同步"
            state="loading"
            variant="pill"
          />
          <View className={styles['newsLoadingBriefing'] ?? ''}>
            <View className={styles['newsLoadingCrest'] ?? ''} />
            <View className={styles['newsLoadingCopy'] ?? ''}>
              <View className={styles['skeletonStrong'] ?? ''} />
              <View className={styles['skeletonLine'] ?? ''} />
              <View className={styles['skeletonShort'] ?? ''} />
            </View>
          </View>
          <View className={styles['newsLoadingMetrics'] ?? ''}>
            {Array.from({ length: 4 }, (_, index) => (
              <View key={`metric-${index}`} className={styles['newsLoadingMetric'] ?? ''}>
                <View className={styles['skeletonShort'] ?? ''} />
                <View className={styles['skeletonStrong'] ?? ''} />
              </View>
            ))}
          </View>
        </WowPanel>
        <FeaturedCarousel items={[]} loading />
        <View className={styles['section'] ?? ''}>
          <SectionTitle>频道</SectionTitle>
          <ChannelDock items={[]} loading />
        </View>
        <WowPanel title="重点更新" variant="raised">
          <RankedFeed emptyText="" items={[]} loading loadingRows={3} />
        </WowPanel>
      </View>
    )
  }
  const detail = state.state === 'loading'
    ? loadingText
    : state.state === 'empty'
      ? emptyText
      : state.state === 'error'
        ? state.error
        : state.state === 'blocked'
          ? state.reason
          : state.reason
  return (
    <WowPanel variant={state.state === 'error' || state.state === 'blocked' ? 'danger' : 'inset'}>
      <View className={styles['statePanel'] ?? ''} data-route-state={state.state}>
        <StatusVisual detail={detail} state={state.state} variant="pill" />
        {(state.state === 'error' || state.state === 'blocked') && onRetry ? (
          <ActionButton variant="secondaryMetal" onClick={onRetry}>重试</ActionButton>
        ) : null}
      </View>
    </WowPanel>
  )
}

export function StaleNotice<T>({ state }: { state: RouteDataState<T> }) {
  if (state.state !== 'stale') return null
  return (
    <View className={styles['staleNotice'] ?? ''}>
      <StatusVisual detail={state.staleReason} glyph="row" state="stale" variant="pill" />
    </View>
  )
}

export function goBack(fallbackTab = '/pages/news/news'): void {
  const pages = Taro.getCurrentPages()
  if (pages.length > 1) {
    void Taro.navigateBack()
    return
  }
  if (TAB_ROUTES.has(fallbackTab)) {
    void Taro.switchTab({ url: fallbackTab })
    return
  }
  void Taro.redirectTo({ url: fallbackTab })
}

export function navigateTo(path: string, params: Readonly<Record<string, string | undefined>> = {}): void {
  const query = Object.entries(params)
    .filter((entry): entry is [string, string] => typeof entry[1] === 'string' && entry[1].length > 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
  void Taro.navigateTo({ url: `${path}${query ? `?${query}` : ''}` })
}

export async function copyText(value: string, successTitle = '已复制'): Promise<void> {
  if (!value) return
  await Taro.setClipboardData({ data: value })
  await Taro.showToast({ title: successTitle, icon: 'none' })
}

export function safeDecode(value: string | undefined): string {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export function SectionTitle({ children }: { children: string }) {
  return <Text className={styles['sectionTitle'] ?? ''}>{children}</Text>
}
