import Taro, { usePullDownRefresh } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { BuildClassSelector } from '@wow-mini/design-system/components/BuildClassSelector'
import { BuildCommandDeck } from '@wow-mini/design-system/components/BuildCommandDeck'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteColumn, RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { RouteStatePanel } from '@wow-mini/design-system/components/ReconstructionPrimitives'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'

import { readBuildsHomeContext, selectBuildsHomeClass } from '../_shared/build-context-storage'
import { navigateTo, useAsyncRoute } from '../_shared/route-runtime'
import { useTabRootIdentity } from '../../use-tab-root-identity'
import { buildBuildsHomeModel, type BuildsHomeCommandId } from './builds-home-model'
import styles from './builds-home.module.scss'

export default function BuildsHomePage() {
  useTabRootIdentity('pages/builds/builds')
  const [context, setContext] = useState(() => readBuildsHomeContext())
  const route = useAsyncRoute(
    () => wowApi.builds.home(),
    {
      fallbackPolicy: 'blocked',
      isEmpty: (payload) => !payload.classOptions.some((classItem) => classItem.specializations.length > 0),
    },
  )

  usePullDownRefresh(() => {
    void route.load().finally(() => Taro.stopPullDownRefresh())
  })

  const model = useMemo(() => buildBuildsHomeModel({
    routeState: route.state.state,
    context,
    ...(route.data ? { payload: route.data } : {}),
  }), [context, route.data, route.state.state])

  // The page is the adapter boundary: Task 3 publishes classKey while the
  // shared selector intentionally consumes the generic option id contract.
  const classOptions = useMemo(() => model.classOptions.map(({ classKey, ...option }) => ({
    ...option,
    id: classKey,
  })), [model.classOptions])

  const selectClass = (classKey: string) => {
    const nextContext = selectBuildsHomeClass(classKey)
    setContext(nextContext)
  }

  const openCommand = (id: BuildsHomeCommandId) => {
    const item = model.commandItems.find((candidate) => candidate.id === id)
    if (!item || item.disabled || (id !== 'tasks' && !item.specId)) return

    const specializationParams = id === 'tasks' ? {} : { spec: item.specId }
    void wowApi.analytics.track('builds_query_open', {
      queryKey: id,
      ...(id === 'tasks' ? {} : { specId: item.specId }),
    }, 'pages/builds/builds')

    if (id === 'talents') {
      navigateTo('/pages/builds/talent-simulator', specializationParams)
      return
    }
    if (id === 'gear') {
      navigateTo('/pages/builds/detail', { ...specializationParams, query: 'gear' })
      return
    }
    if (id === 'simc') {
      navigateTo('/pages/simulator/simc', { ...specializationParams, from: 'builds' })
      return
    }
    if (id === 'tasks') {
      navigateTo('/pages/simulator/tasks', { from: 'builds' })
    }
  }

  const ready = Boolean(route.data && model.selectedClassKey && model.launchSpecId)
  const unavailableState = route.state.state === 'error'
    ? 'error'
    : route.state.state === 'loading'
      ? 'loading'
      : 'blocked'
  const unavailableDetail = route.state.state === 'error'
    ? route.state.error
    : route.state.state === 'blocked'
      ? route.state.reason
      : route.state.state === 'loading'
        ? '正在读取可用职业与专精映射'
        : '没有可用的职业专精映射'

  return (
    <AppShell bodyScrollable={false} tabRoot>
      <RouteStage
        className={styles['page'] ?? ''}
        routeState={ready ? route.state.state : unavailableState}
        targetRegionCount={4}
        width="full"
      >
        <PageFrame
          region="page_header"
          title="职业专精"
          variant="builds-home"
        >
          <RouteColumn
            className={styles['surface'] ?? ''}
            routeState={ready ? route.state.state : unavailableState}
          >
            {ready ? (
              <RouteRegion className={styles['classSelectorRegion'] ?? ''} data-region="class_selector">
                <BuildClassSelector
                  options={classOptions}
                  value={model.selectedClassKey ?? ''}
                  onSelect={selectClass}
                />
              </RouteRegion>
            ) : null}
            <RouteRegion className={styles['commandDeckRegion'] ?? ''} data-region="command_deck">
              {ready ? (
                <BuildCommandDeck items={model.commandItems} onSelect={openCommand} />
              ) : (
                <RouteStatePanel
                  actionLabel={unavailableState === 'loading' ? undefined : '重试'}
                  detail={unavailableDetail}
                  region="builds_home_route_state"
                  state={unavailableState}
                  title={unavailableState === 'loading' ? '正在加载职业目录' : '职业目录暂不可用'}
                  variant="page"
                  onAction={unavailableState === 'loading' ? undefined : route.load}
                />
              )}
            </RouteRegion>
          </RouteColumn>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
