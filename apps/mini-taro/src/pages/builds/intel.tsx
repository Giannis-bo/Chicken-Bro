import { ScrollView, View } from '@tarojs/components'
import { useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  BuildIntelCard,
  BuildIntelDisclaimer,
  BuildIntelFilterBar,
  BuildIntelSummary,
} from '@wow-mini/design-system/components/BuildIntelComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteColumn, RouteFlow } from '@wow-mini/design-system/components/RouteFlow'
import type { RouteDataState } from '@wow-mini/domain'

import {
  copyText,
  goBack,
  navigateTo,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  buildBuildIntelModel,
  type BuildIntelCardAction,
  type BuildIntelCardView,
  type BuildIntelFilterId,
  type BuildIntelSortId,
} from './build-intel-model'
import styles from './build-intel.module.scss'

function routeReason(state: RouteDataState<unknown>): string | undefined {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  if (state.state === 'unknown') return state.reason
  return undefined
}

const visibleRegions = ['build_card_a', 'build_card_b', 'build_card_c'] as const

export default function BuildIntelPage() {
  const [activeFilter, setActiveFilter] = useState<BuildIntelFilterId>('all')
  const [sortId, setSortId] = useState<BuildIntelSortId>('source')
  const route = useAsyncRoute(
    () => wowApi.builds.intel(),
    { fallbackPolicy: 'stale', isEmpty: (value) => value.items.length === 0 },
  )
  const currentRouteReason = routeReason(route.state)
  const model = buildBuildIntelModel({
    ...(route.data ? { payload: route.data } : {}),
    routeState: route.state.state,
    activeFilter,
    sortId,
    ...(currentRouteReason ? { routeReason: currentRouteReason } : {}),
  })

  const cycleFilter = () => {
    const available = model.filters.filter((filter) => filter.id === 'all' || filter.count > 0)
    const currentIndex = available.findIndex((filter) => filter.id === activeFilter)
    const next = available[(currentIndex + 1) % available.length]
    setActiveFilter(next?.id ?? 'all')
  }

  const runAction = (action: BuildIntelCardAction, card: BuildIntelCardView) => {
    if (action === 'simulator' && card.specId) {
      navigateTo('/pages/builds/talent-simulator', { spec: card.specId })
      return
    }
    if (action === 'copy_source' && card.sourceUrl) {
      copyText(card.sourceUrl, '来源链接已复制')
      return
    }
    if (action === 'retry') {
      void route.load()
      return
    }
    if (action === 'reset_filter') setActiveFilter('all')
  }

  return (
    <AppShell
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.build-intel-surface"
    >
      <RouteFlow className={styles['page'] ?? ''} routeState={route.state.state}>
        <PageFrame
          backRegion="top_bar.back-control"
          region="top_bar"
          title="构筑情报"
          variant="build-intel"
          onBack={() => goBack('/pages/builds/builds')}
        >
          <RouteColumn>
            <View className={styles['summary'] ?? ''}>
              <BuildIntelSummary
                description={model.description}
                loading={model.initialLoading}
                recordCountLabel={model.recordCountLabel}
                state={model.state}
                stateLabel={model.stateLabel}
                title={model.title}
              />
            </View>
            <View className={styles['filter'] ?? ''}>
              <BuildIntelFilterBar
                disabled={model.initialLoading}
                filterLabel={model.filterLabel}
                sortLabel={model.sortLabel}
                onFilter={cycleFilter}
                onSort={() => setSortId((current) => current === 'source' ? 'name' : 'source')}
              />
            </View>
            <View className={styles['cardViewport'] ?? ''} data-owner="build-intel-card-viewport">
              <ScrollView
                className={styles['cardScroll'] ?? ''}
                data-card-count={model.cards.length}
                data-role="build-intel-card-scroll"
                scrollY
              >
                <View className={styles['cardStack'] ?? ''}>
                  {model.cards.map((card, index) => (
                    <View
                      key={card.id}
                      className={[
                        styles['cardSlot'] ?? '',
                        index === 0 ? styles['cardSlotFirst'] ?? '' : '',
                        index === 1 ? styles['cardSlotSecond'] ?? '' : '',
                        index >= 2 ? styles['cardSlotFollowing'] ?? '' : '',
                      ].filter(Boolean).join(' ')}
                      data-region={visibleRegions[index] ?? 'build_card_overflow'}
                      data-visible-slot={index < model.visibleCardSlotCount ? 'true' : 'false'}
                    >
                      <BuildIntelCard
                        description={card.description}
                        iconUrl={card.iconUrl}
                        id={card.id}
                        loading={card.loading}
                        metadata={card.metadata}
                        primaryDisabled={card.primaryAction === 'none'}
                        primaryLabel={card.primaryLabel}
                        secondaryDisabled={card.secondaryAction === 'none'}
                        secondaryLabel={card.secondaryLabel}
                        state={card.state}
                        stateLabel={card.stateLabel}
                        title={card.title}
                        {...(card.primaryAction !== 'none' ? {
                          onPrimary: () => runAction(card.primaryAction, card),
                        } : {})}
                        {...(card.secondaryAction !== 'none' ? {
                          onSecondary: () => runAction(card.secondaryAction, card),
                        } : {})}
                      />
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
            <View className={styles['disclaimer'] ?? ''}>
              <BuildIntelDisclaimer copy={model.disclaimer} />
            </View>
          </RouteColumn>
        </PageFrame>
      </RouteFlow>
    </AppShell>
  )
}
