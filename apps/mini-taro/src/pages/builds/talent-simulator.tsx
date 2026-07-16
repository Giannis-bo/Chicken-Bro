import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import {
  AppShell,
  PageFrame,
  TalentActionBar,
  TalentCommunityRow,
  TalentGraphViewport,
  TalentImportStatus,
  TalentLegend,
  TalentPointSummary,
  TalentSelectorPanel,
  TalentTreeTabs,
  type TalentActionItem,
  type TalentGraphNodeItem,
  type TalentImportStatusItem,
  type TalentSelectorItem,
  type TalentSelectorOption,
  type TalentTreeTabItem,
} from '@wow-mini/design-system'
import type {
  BuildsHomePayload,
  ReadinessState,
  RouteDataState,
  TalentImportPayload,
  WebsimBootstrapPayload,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  type SpecSelection,
} from '../_shared/build-context'
import {
  copyText,
  goBack,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  activeTalentNodes,
  activeTalentSection,
  buildTalentGraph,
  cycleTalentRank,
  initialTalentRanks,
  talentPoints,
} from './talent-simulator-model'
import styles from './talent-simulator.module.scss'

interface TalentPagePayload {
  home: BuildsHomePayload
  bootstrap: WebsimBootstrapPayload
  selection: SpecSelection
  talents: WebsimTalentsPayload
  talentImport: TalentImportPayload
}

const placeholderSelectors: readonly TalentSelectorItem[] = [
  { id: 'class', label: '职业', value: '读取中', options: [], selectedIndex: 0, disabled: true },
  { id: 'spec', label: '专精', value: '读取中', options: [], selectedIndex: 0, disabled: true },
  { id: 'hero', label: '英雄', value: '读取中', options: [], selectedIndex: 0, disabled: true },
]

const placeholderTabs: readonly TalentTreeTabItem[] = [
  { id: 'class', label: '职业天赋' },
  { id: 'spec', label: '专精天赋' },
  { id: 'hero', label: '英雄天赋' },
]

function routeReason(state: RouteDataState<unknown>): string {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  if (state.state === 'unknown') return state.reason
  return ''
}

function graphRouteState(state: ReadinessState, data: TalentPagePayload | undefined): ReadinessState {
  if (!data) return state
  if (state === 'loading') return 'stale'
  return state
}

export default function TalentSimulatorPage() {
  const router = useRouter()
  const [selectedSpecId, setSelectedSpecId] = useState(safeDecode(router.params['spec']) || defaultSpecId)
  const [activeTree, setActiveTree] = useState('class')
  const [ranks, setRanks] = useState<Readonly<Record<string, number>>>({})
  const [saving, setSaving] = useState(false)
  const selectionChanged = useRef(false)
  const route = useAsyncRoute<TalentPagePayload>(async () => {
    const [homeResult, bootstrapResult] = await Promise.all([
      wowApi.builds.home(),
      wowApi.websim.bootstrap(),
    ])
    const selection = findSpecSelection(homeResult.payload, selectedSpecId)
    if (!selection) throw new Error('没有可用的职业专精映射')
    const request = {
      classKey: selection.classKey,
      specKey: selection.specKey,
      ...(selection.heroKey ? { heroKey: selection.heroKey } : {}),
    }
    const [talentResult, importResult] = await Promise.all([
      wowApi.websim.talents(request),
      wowApi.websim.talentImport(request),
    ])
    const errors = [
      homeResult.error,
      bootstrapResult.error,
      talentResult.error,
      importResult.error,
    ].filter(Boolean)
    return {
      payload: {
        home: homeResult.payload,
        bootstrap: bootstrapResult.payload,
        selection,
        talents: talentResult.payload,
        talentImport: importResult.payload,
      },
      fromFallback: homeResult.fromFallback
        || bootstrapResult.fromFallback
        || talentResult.fromFallback
        || importResult.fromFallback,
      error: errors.join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    void route.load()
  }, [selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    setRanks(initialTalentRanks(route.data.talents.nodes))
    setActiveTree(route.data.talents.treeSections[0]?.key || 'class')
  }, [route.data])

  const data = route.data
  const activeNodes = activeTalentNodes(data?.talents, activeTree)
  const activeSection = activeTalentSection(data?.talents, activeTree)
  const points = talentPoints(activeNodes, activeSection, ranks)
  const initialLoading = route.state.state === 'loading' && !data
  const dependencyRefCount = activeNodes.reduce(
    (total, node) => total + (node.prerequisiteIds?.length ?? 0),
    0,
  )
  const connectivityStatus = initialLoading
    ? 'loading'
    : dependencyRefCount > 0
      ? 'ready'
      : 'unavailable'
  const graph = buildTalentGraph({
    nodes: activeNodes,
    ranks,
    routeState: connectivityStatus === 'unavailable'
      ? 'blocked'
      : graphRouteState(route.state.state, data),
    loading: initialLoading || activeNodes.length === 0,
  })
  const importReady = data?.talentImport.status === 'verified'
    && Boolean(data.talentImport.importCode)
  const readiness = data?.talents.talentReadiness

  const classOptions: readonly TalentSelectorOption[] = (data?.home.classOptions ?? []).map((classItem) => ({
    id: classItem.specializations[0]?.id ?? classItem.websimClassKey ?? classItem.name,
    label: classItem.name,
  }))
  const specOptions: readonly TalentSelectorOption[] = (data?.selection.classItem.specializations ?? []).map((spec) => ({
    id: spec.id || spec.specId || '',
    label: spec.specName || spec.title || spec.name,
  })).filter((option) => option.id)
  const heroSection = data?.talents.treeSections.find((section) => section.key === 'hero')
  const heroOptions: readonly TalentSelectorOption[] = heroSection
    ? [{ id: data?.talents.heroKey || 'hero', label: heroSection.title }]
    : []

  const selectors: readonly TalentSelectorItem[] = data ? [
    {
      id: 'class',
      label: '职业',
      value: data.selection.classItem.name,
      options: classOptions,
      selectedIndex: Math.max(0, classOptions.findIndex((item) => item.label === data.selection.classItem.name)),
      ...(data.selection.classItem.iconUrl ? { iconUrl: data.selection.classItem.iconUrl } : {}),
    },
    {
      id: 'spec',
      label: '专精',
      value: data.selection.spec.specName || data.selection.spec.title || data.selection.spec.name,
      options: specOptions,
      selectedIndex: Math.max(0, specOptions.findIndex((item) => item.id === data.selection.specId)),
      ...((data.selection.spec.specIconUrl || data.selection.spec.iconUrl)
        ? { iconUrl: data.selection.spec.specIconUrl || data.selection.spec.iconUrl }
        : {}),
    },
    {
      id: 'hero',
      label: '英雄',
      value: heroSection?.title ?? '未提供',
      options: heroOptions,
      selectedIndex: 0,
      disabled: heroOptions.length < 2,
    },
  ] : placeholderSelectors

  const tabs: readonly TalentTreeTabItem[] = data
    ? data.talents.treeSections.map((section) => ({
        id: section.key,
        label: section.key === 'class'
          ? '职业天赋'
          : section.key === 'spec'
            ? '专精天赋'
            : '英雄天赋',
      }))
    : placeholderTabs

  const importStatuses: readonly TalentImportStatusItem[] = [
    {
      id: 'evidence',
      label: initialLoading
        ? '读取中'
        : connectivityStatus === 'unavailable'
          ? '连接规则待核验'
          : readiness?.spellReady ? '证据完整' : '部分证据',
      state: connectivityStatus === 'unavailable' ? 'partial' : readiness?.spellReady ? 'ready' : 'partial',
    },
    {
      id: 'encoding',
      label: initialLoading ? '读取中' : readiness?.encodingReady ? '编码规则可用' : '待编码',
      state: readiness?.encodingReady ? 'ready' : 'partial',
    },
    {
      id: 'import',
      label: initialLoading ? '读取中' : importReady ? '可导入' : '导入不可用',
      state: importReady ? 'ready' : 'blocked',
    },
  ]

  const selectOption = (item: TalentSelectorItem, option: TalentSelectorOption) => {
    if (item.id === 'class' || item.id === 'spec') setSelectedSpecId(option.id)
  }

  const selectNode = (node: TalentGraphNodeItem) => {
    setRanks((current) => cycleTalentRank({
      nodeId: node.id,
      nodes: activeNodes,
      ranks: current,
      pointCap: points.cap,
    }))
  }

  const saveImportTemplate = async () => {
    if (!data || !importReady) return
    setSaving(true)
    try {
      const result = await wowApi.templates.upsert({
        type: 'talent',
        title: `${data.selection.label} · 社区导入`,
        classKey: data.selection.classKey,
        className: data.selection.classItem.name,
        specKey: data.selection.specKey,
        specName: data.selection.spec.specName || data.selection.spec.name,
        heroKey: data.talents.heroKey || data.selection.heroKey,
        rawString: data.talentImport.importCode,
        status: 'encoded',
        statusLabel: '已编码',
        source: data.talentImport.source,
        metadata: { sourceStatus: data.talentImport.status },
      })
      await Taro.showToast({
        title: result.payload.template ? '模板已保存' : '保存失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  const currentReason = routeReason(route.state)
  const resetRanks = () => setRanks(initialTalentRanks(data?.talents.nodes ?? []))
  const communityCount = (data?.talents.communityTemplates.length ?? 0)
    + (data?.talents.presets.length ?? 0)

  const actions: readonly TalentActionItem[] = route.state.state === 'error' && !data
    ? [
        { id: 'save', label: '重试', tone: 'gold', onClick: () => void route.load() },
        { id: 'import', label: '导入', tone: 'blue', disabled: true, onClick: () => undefined },
        { id: 'reset', label: '重置', tone: 'metal', disabled: true, onClick: () => undefined },
      ]
    : [
        {
          id: 'save',
          label: saving ? '保存中' : '保存模板',
          tone: 'gold',
          disabled: !importReady || saving,
          onClick: () => void saveImportTemplate(),
        },
        {
          id: 'import',
          label: '导入',
          tone: 'blue',
          disabled: !importReady,
          onClick: () => {
            if (data?.talentImport.importCode) void copyText(data.talentImport.importCode, '已复制验证导入码')
          },
        },
        {
          id: 'reset',
          label: '重置',
          tone: 'metal',
          disabled: !data || route.state.state === 'loading',
          onClick: resetRanks,
        },
      ]

  return (
    <AppShell
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.talent-simulator-surface"
    >
      <View
        className={styles['pageFrame'] ?? ''}
        data-route-state={route.state.state}
        data-target-region-count="10"
      >
        <PageFrame
          backRegion="top_bar.back-control"
          region="top_bar"
          title="天赋构筑"
          variant="talent-simulator"
          onBack={() => goBack('/pages/builds/builds')}
        >
          <View className={styles['surface'] ?? ''}>
            <View className={styles['selectorRegion'] ?? ''}>
              <TalentSelectorPanel
                items={selectors}
                loading={initialLoading}
                onSelect={selectOption}
              />
            </View>
            <View className={styles['tabsRegion'] ?? ''}>
              <TalentTreeTabs
                activeId={activeTree}
                items={tabs}
                loading={initialLoading}
                onSelect={(item) => setActiveTree(item.id)}
              />
            </View>
            <View className={styles['pointsRegion'] ?? ''}>
              <TalentPointSummary
                cap={points.cap}
                loading={initialLoading}
                remaining={points.remaining}
                spent={points.spent}
              />
            </View>
            <View className={styles['graphRegion'] ?? ''}>
              <TalentGraphViewport
                key={activeTree}
                connectivityStatus={connectivityStatus}
                edges={graph.edges}
                nodeCount={graph.nodeCount}
                nodes={graph.nodes}
                planeHeight={graph.planeHeight}
                planeWidth={graph.planeWidth}
                readonly={route.state.state !== 'ready' || connectivityStatus !== 'ready'}
                uniquePositionCount={graph.uniquePositionCount}
                onNode={selectNode}
              />
            </View>
            <View className={styles['legendRegion'] ?? ''}><TalentLegend /></View>
            <View className={styles['importRegion'] ?? ''}>
              <TalentImportStatus
                detail={currentReason || (connectivityStatus === 'unavailable'
                  ? '上游未返回天赋连接关系，当前树只读'
                  : importReady ? '已取得后端验证导入码' : '后端未返回可用导入码')}
                headline={importReady ? '已导入构筑' : '未导入构筑'}
                loading={initialLoading}
                statuses={importStatuses}
                title="WebSim 构筑"
                {...(importReady && data ? {
                  onOpen: () => void copyText(data.talentImport.importCode, '已复制验证导入码'),
                } : {})}
              />
            </View>
            <View className={styles['communityRegion'] ?? ''}>
              <TalentCommunityRow
                detail={initialLoading
                  ? '正在读取来源模板'
                  : `${communityCount} 份来源模板 · ${importReady ? '已验证' : '暂不可应用'}`}
                disabled={initialLoading}
                title="社区模板"
                onClick={() => {
                  void Taro.showToast({
                    title: importReady ? '模板导入证据可用' : '来源模板尚无可应用导入码',
                    icon: 'none',
                  })
                }}
              />
            </View>
            <View className={styles['actionsRegion'] ?? ''}><TalentActionBar items={actions} /></View>
          </View>
        </PageFrame>
      </View>
    </AppShell>
  )
}
