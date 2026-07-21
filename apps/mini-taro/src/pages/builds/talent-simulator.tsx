import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import {
  TalentActionBar,
  TalentGraphViewport,
  TalentLegend,
  TalentPointSummary,
  TalentSelectorPanel,
  TalentTemplateImportSheet,
  TalentTemplateNameSheet,
  TalentTreeTabs,
  type TalentActionItem,
  type TalentGraphNodeItem,
  type TalentSelectorItem,
  type TalentSelectorOption,
  type TalentTemplateCommunityWinner,
  type TalentTemplateSavedImportItem,
  type TalentTreeTabItem,
} from '@wow-mini/design-system/components/TalentSimulatorComponents'
import type {
  BuildTemplate,
  BuildsHomePayload,
  ReadinessState,
  TalentNodeAvailabilityPayload,
  WebsimBootstrapPayload,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  type SpecSelection,
} from '../_shared/build-context'
import { rememberBuildsHomeSpec } from '../_shared/build-context-storage'
import {
  goBack,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  activeTalentNodes,
  activeTalentSection,
  applyTalentValidation,
  buildTalentGraph,
  communityTalentRegionLabel,
  communityTalentTemplateHasPlayerChoices,
  communityTalentWinnerForImport,
  defaultTalentTemplateTitle,
  heroTalentIcon,
  heroTalentOptions,
  initialTalentRanks,
  proposeTalentChoice,
  proposeTalentRank,
  runFencedTalentSave,
  talentPoints,
} from './talent-simulator-model'
import styles from './talent-simulator.module.scss'

interface TalentPagePayload {
  home: BuildsHomePayload
  bootstrap: WebsimBootstrapPayload
  selection: SpecSelection
  talents: WebsimTalentsPayload
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

function graphRouteState(state: ReadinessState, data: TalentPagePayload | undefined): ReadinessState {
  if (!data) return state
  if (state === 'loading') return 'stale'
  return state
}

function templateUpdatedAt(value: string | undefined): string {
  if (!value) return '未提供'
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return value
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export default function TalentSimulatorPage() {
  const router = useRouter()
  const [selectedSpecId, setSelectedSpecId] = useState(safeDecode(router.params['spec']) || defaultSpecId)
  const [selectedHeroKey, setSelectedHeroKey] = useState(safeDecode(router.params['hero']) || '')
  const [activeTree, setActiveTree] = useState('class')
  const [ranks, setRanks] = useState<Readonly<Record<string, number>>>({})
  const [nodeAvailability, setNodeAvailability] = useState<TalentNodeAvailabilityPayload | undefined>()
  const [validating, setValidating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [nameSheetOpen, setNameSheetOpen] = useState(false)
  const [templateTitle, setTemplateTitle] = useState('')
  const [importSheet, setImportSheet] = useState<'closed' | 'saved' | 'community'>('closed')
  const [savedTemplates, setSavedTemplates] = useState<readonly BuildTemplate[]>([])
  const [loadingSavedTemplates, setLoadingSavedTemplates] = useState(false)
  const [importingTemplate, setImportingTemplate] = useState(false)
  const selectionChanged = useRef(false)
  const validationSequence = useRef(0)
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
      ...(selectedHeroKey || selection.heroKey
        ? { heroKey: selectedHeroKey || selection.heroKey }
        : {}),
    }
    const talentResult = await wowApi.websim.talents(request)
    const errors = [
      homeResult.error,
      bootstrapResult.error,
      talentResult.error,
    ].filter(Boolean)
    return {
      payload: {
        home: homeResult.payload,
        bootstrap: bootstrapResult.payload,
        selection,
        talents: talentResult.payload,
      },
      fromFallback: homeResult.fromFallback
        || bootstrapResult.fromFallback
        || talentResult.fromFallback,
      error: errors.join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    void route.load()
  }, [selectedHeroKey, selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    validationSequence.current += 1
    setRanks(initialTalentRanks(route.data.talents.nodes))
    setNodeAvailability(route.data.talents.nodeAvailability)
    setActiveTree(route.data.talents.treeSections[0]?.key || 'class')
    setValidating(false)
    setSaving(false)
    setNameSheetOpen(false)
    setImportSheet('closed')
  }, [route.data])

  const data = route.data
  const resolvedClassKey = data?.selection.classKey
  const resolvedSpecId = data?.selection.specId
  useEffect(() => {
    if (!data?.selection || !resolvedClassKey || !resolvedSpecId) return
    rememberBuildsHomeSpec(data.selection)
  }, [resolvedClassKey, resolvedSpecId])

  const currentHeroKey = data?.talents.heroKey || selectedHeroKey || data?.selection.heroKey || ''
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
    ...(nodeAvailability ? { availability: nodeAvailability } : {}),
    routeState: connectivityStatus === 'unavailable'
      ? 'blocked'
      : graphRouteState(route.state.state, data),
    loading: initialLoading || activeNodes.length === 0,
    layoutMode: 'source_lattice',
  })
  const classOptions: readonly TalentSelectorOption[] = (data?.home.classOptions ?? []).map((classItem) => ({
    id: classItem.specializations[0]?.id ?? classItem.websimClassKey ?? classItem.name,
    label: classItem.name,
  }))
  const specOptions: readonly TalentSelectorOption[] = (data?.selection.classItem.specializations ?? []).map((spec) => ({
    id: spec.id || spec.specId || '',
    label: spec.specName || spec.title || spec.name,
  })).filter((option) => option.id)
  const heroSection = data?.talents.treeSections.find((section) => section.key === 'hero')
  const heroOptions: readonly TalentSelectorOption[] = heroTalentOptions(data?.bootstrap, data?.selection)
    .map((hero) => ({ id: hero.key, label: hero.label }))
  const currentHero = heroOptions.find((option) => option.id === currentHeroKey)
  const heroIconUrl = heroTalentIcon(data?.talents.nodes ?? [])
  const communityWinner = communityTalentWinnerForImport(
    data?.talents.communityTemplates ?? [],
    data?.talents.heroKey || data?.selection.heroKey,
  )
  const savedImportItems: readonly TalentTemplateSavedImportItem[] = savedTemplates.map((template) => ({
    id: template.id,
    title: template.title,
    detail: `更新：${templateUpdatedAt(template.updatedAt)}`,
  }))
  const communityWinnerView: TalentTemplateCommunityWinner | undefined = communityWinner ? {
    title: communityWinner.name || communityWinner.title || '社区天赋模板',
    playerName: communityWinner.playerName || '未提供',
    serverName: communityWinner.serverName || '未提供',
    region: communityTalentRegionLabel(communityWinner.region),
    ...(typeof communityWinner.mplusScore === 'number' && communityWinner.mplusScore > 0
      ? { mplusScore: communityWinner.mplusScore }
      : {}),
    updatedAt: templateUpdatedAt(communityWinner.updatedAt),
    sourceName: communityWinner.sourceName || communityWinner.source || '未提供',
    isStale: communityWinner.isStale === true || communityWinner.freshnessStatus === 'stale',
    importable: communityWinner.canApplyVisual === true,
  } : undefined

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
      value: currentHero?.label ?? heroSection?.title ?? '未提供',
      options: heroOptions,
      selectedIndex: Math.max(0, heroOptions.findIndex((option) => option.id === currentHeroKey)),
      disabled: heroOptions.length < 2,
      ...(heroIconUrl ? { iconUrl: heroIconUrl } : {}),
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

  const selectOption = (item: TalentSelectorItem, option: TalentSelectorOption) => {
    if (item.id === 'class' || item.id === 'spec') {
      validationSequence.current += 1
      setValidating(false)
      setSaving(false)
      setSelectedHeroKey('')
      setSelectedSpecId(option.id)
      return
    }
    if (item.id === 'hero') {
      validationSequence.current += 1
      setValidating(false)
      setSaving(false)
      setSelectedHeroKey(option.id)
    }
  }

  const talentEditRequest = (proposedRanks: Readonly<Record<string, number>>) => {
    if (!data) return null
    return {
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      ...(data.talents.heroKey || data.selection.heroKey
        ? { heroKey: data.talents.heroKey || data.selection.heroKey }
        : {}),
      talentState: {
        selectedNodes: Object.entries(proposedRanks)
          .filter(([, rank]) => rank > 0)
          .map(([id, rank]) => ({ id, rank })),
      },
    }
  }

  const submitTalentProposal = async (proposal: Readonly<Record<string, number>>) => {
    const request = talentEditRequest(proposal)
    if (!request) return
    const sequence = validationSequence.current + 1
    validationSequence.current = sequence
    setValidating(true)
    const result = await wowApi.websim.talentValidate(request)
    if (validationSequence.current !== sequence) return
    const decision = applyTalentValidation(ranks, result.payload, result.fromFallback, result.error)
    setValidating(false)
    if (decision.accepted) {
      setRanks(decision.ranks)
      setNodeAvailability(result.payload.nodeAvailability)
      return
    }
    await Taro.showToast({ title: decision.error, icon: 'none' })
  }

  const selectNode = (node: TalentGraphNodeItem) => {
    if (node.choiceOptionIds.length > 1) {
      const choices = node.choiceOptionIds
        .map((id) => activeNodes.find((candidate) => candidate.id === id))
        .filter((candidate): candidate is NonNullable<typeof candidate> => Boolean(candidate))
      if (choices.length > 1) {
        void Taro.showActionSheet({
          itemList: choices.map((choice) => choice.name),
          success: ({ tapIndex }) => {
            const choice = choices[tapIndex]
            if (!choice) return
            void submitTalentProposal(proposeTalentChoice({
              nodeId: choice.id,
              nodes: activeNodes,
              ranks,
            }))
          },
        })
        return
      }
    }
    void submitTalentProposal(proposeTalentRank({
      nodeId: node.id,
      nodes: activeNodes,
      ranks,
    }))
  }

  const exportCurrentTalent = async (operationSequence?: number) => {
    const request = talentEditRequest(ranks)
    if (!request) return null
    const sequence = operationSequence ?? validationSequence.current + 1
    if (operationSequence === undefined) validationSequence.current = sequence
    setValidating(true)
    const result = await wowApi.websim.talentExport(request)
    if (validationSequence.current !== sequence) return null
    setValidating(false)
    const decision = applyTalentValidation(ranks, result.payload.validation, result.fromFallback, result.error)
    const code = result.payload.websimExportCode.trim()
    if (!decision.accepted || !code) {
      const error = decision.error || '后端未返回当前构筑的导出码'
      await Taro.showToast({ title: error, icon: 'none' })
      return null
    }
    setRanks(decision.ranks)
    setNodeAvailability(result.payload.validation.nodeAvailability)
    return { code, validation: result.payload.validation }
  }

  const saveImportTemplate = async () => {
    if (!data) return
    const title = templateTitle.trim()
    if (!title) {
      await Taro.showToast({ title: '请填写模板名称', icon: 'none' })
      return
    }
    const operationSequence = validationSequence.current + 1
    validationSequence.current = operationSequence
    setSaving(true)
    try {
      await runFencedTalentSave({
        isCurrent: () => validationSequence.current === operationSequence,
        exportCurrent: () => exportCurrentTalent(operationSequence),
        persist: (exportDecision) => wowApi.templates.upsert({
          type: 'talent',
          title,
          classKey: data.selection.classKey,
          className: data.selection.classItem.name,
          specKey: data.selection.specKey,
          specName: data.selection.spec.specName || data.selection.spec.name,
          heroKey: data.talents.heroKey || data.selection.heroKey,
          rawString: exportDecision.code,
          status: 'encoded',
          statusLabel: '已编码',
          source: 'WebSim 天赋模拟器',
          metadata: {
            exportAuthority: 'backend',
            talentSchemaRevision: exportDecision.validation.talentSchemaRevision,
            validationStatus: exportDecision.validation.status,
          },
        }),
        complete: async (result) => {
          const template = result.payload.template
          setSavedTemplates(result.payload.templates.filter((item) => item.type === 'talent'))
          const savedLocally = template?.trust.level === 'local_only' || result.fromFallback
          const title = !template
            ? '保存失败'
            : savedLocally
              ? '已保存到本地，远端未确认'
              : '模板已保存并由远端确认'
          await Taro.showToast({ title, icon: 'none' })
          if (template) setNameSheetOpen(false)
        },
      })
    } finally {
      if (validationSequence.current === operationSequence) setSaving(false)
    }
  }

  const openNameSheet = () => {
    if (!data) return
    setTemplateTitle(defaultTalentTemplateTitle({
      classLabel: data.selection.classItem.name,
      specLabel: data.selection.spec.specName || data.selection.spec.title || data.selection.spec.name,
      heroLabel: currentHero?.label || heroSection?.title || '英雄天赋',
    }))
    setNameSheetOpen(true)
  }

  const openImportSheet = async () => {
    if (!data) return
    setImportSheet('saved')
    setLoadingSavedTemplates(true)
    const result = await wowApi.templates.fetch('talent')
    setSavedTemplates(result.payload.templates.filter((item) => item.type === 'talent'))
    setLoadingSavedTemplates(false)
    if (result.error && result.payload.templates.length === 0) {
      await Taro.showToast({ title: '已保存模板暂不可用', icon: 'none' })
    }
  }

  const applyImportedValidation = async (
    validation: Parameters<typeof applyTalentValidation>[1],
    fromFallback: boolean,
    error: string,
    operationSequence: number,
  ): Promise<boolean> => {
    if (validationSequence.current !== operationSequence) return false
    const decision = applyTalentValidation(ranks, validation, fromFallback, error)
    if (validationSequence.current !== operationSequence) return false
    setValidating(false)
    if (!decision.accepted) {
      await Taro.showToast({ title: decision.error, icon: 'none' })
      return false
    }
    setRanks(decision.ranks)
    setNodeAvailability(validation.nodeAvailability)
    return true
  }

  const importSavedTemplate = async (templateId: string) => {
    if (!data || importingTemplate) return
    const template = savedTemplates.find((item) => item.id === templateId)
    if (!template?.rawString) return
    const operationSequence = validationSequence.current + 1
    validationSequence.current = operationSequence
    setValidating(true)
    setImportingTemplate(true)
    try {
      const result = await wowApi.websim.talentImportCode({
        code: template.rawString,
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        heroKey: data.talents.heroKey || data.selection.heroKey,
      })
      if (await applyImportedValidation(result.payload.validation, result.fromFallback, result.error, operationSequence)) {
        setImportSheet('closed')
        await Taro.showToast({ title: '已导入保存模板', icon: 'none' })
      }
    } finally {
      setImportingTemplate(false)
      if (validationSequence.current === operationSequence) setValidating(false)
    }
  }

  const importCommunityWinner = async () => {
    if (!data || !communityWinner?.talentState || importingTemplate) return
    const operationSequence = validationSequence.current + 1
    validationSequence.current = operationSequence
    setValidating(true)
    setImportingTemplate(true)
    try {
      const heroKey = data.talents.heroKey || data.selection.heroKey
      const latest = await wowApi.websim.talents({
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        ...(heroKey ? { heroKey } : {}),
      })
      if (latest.fromFallback || latest.error) {
        await Taro.showToast({ title: '社区模板刷新失败，请重试', icon: 'none' })
        return
      }
      const latestWinner = communityTalentWinnerForImport(
        latest.payload.communityTemplates,
        heroKey,
        communityWinner.id,
      )
      if (!latestWinner?.talentState) {
        await Taro.showToast({ title: '社区模板已更新，请重新打开导入', icon: 'none' })
        return
      }
      if (!communityTalentTemplateHasPlayerChoices(latestWinner)) {
        await Taro.showToast({ title: '社区模板数据不完整，已阻止导入', icon: 'none' })
        return
      }
      const exportCode = (latestWinner.websimExportCode ?? '').trim()
      if (!exportCode.startsWith('websim:')) {
        await Taro.showToast({ title: '社区模板导入码无效，请稍后重试', icon: 'none' })
        return
      }
      const result = await wowApi.websim.talentImportCode({
        code: exportCode,
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        heroKey,
      })
      if (await applyImportedValidation(result.payload.validation, result.fromFallback, result.error, operationSequence)) {
        setImportSheet('closed')
        await Taro.showToast({ title: '已导入社区模板', icon: 'none' })
      }
    } finally {
      setImportingTemplate(false)
      if (validationSequence.current === operationSequence) setValidating(false)
    }
  }

  const resetRanks = () => void submitTalentProposal(initialTalentRanks(data?.talents.nodes ?? []))

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
          disabled: !data || validating || saving,
          onClick: openNameSheet,
        },
        {
          id: 'import',
          label: '导入',
          tone: 'blue',
          disabled: !data || validating || saving,
          onClick: () => void openImportSheet(),
        },
        {
          id: 'reset',
          label: '重置',
          tone: 'metal',
          disabled: !data || route.state.state === 'loading' || validating || saving,
          onClick: resetRanks,
        },
      ]

  return (
    <AppShell
      bodyScrollable={false}
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.talent-simulator-surface"
    >
      <RouteStage
        className={styles['pageFrame'] ?? ''}
        routeState={route.state.state}
        targetRegionCount={8}
        width="full"
      >
        <PageFrame
          backRegion="top_bar.back-control"
          region="top_bar"
          title="天赋构筑"
          variant="talent-simulator"
          onBack={() => goBack('/pages/builds/builds')}
        >
          <View className={styles['surface'] ?? ''}>
            <RouteRegion className={styles['selectorRegion'] ?? ''} data-region="specialization_selector">
              <TalentSelectorPanel
                items={selectors}
                loading={initialLoading}
                onSelect={selectOption}
              />
            </RouteRegion>
            <RouteRegion className={styles['tabsRegion'] ?? ''} data-region="talent_tabs">
              <TalentTreeTabs
                activeId={activeTree}
                items={tabs}
                loading={initialLoading}
                onSelect={(item) => setActiveTree(item.id)}
              />
            </RouteRegion>
            <RouteRegion className={styles['pointsRegion'] ?? ''} data-region="points_summary">
              <TalentPointSummary
                cap={points.cap}
                loading={initialLoading}
                remaining={points.remaining}
                spent={points.spent}
              />
            </RouteRegion>
            <RouteRegion className={styles['graphRegion'] ?? ''} data-region="talent_graph">
              <TalentGraphViewport
                key={activeTree}
                allowVerticalOverflow
                connectivityStatus={connectivityStatus}
                edges={graph.edges}
                nodeCount={graph.nodeCount}
                nodes={graph.nodes}
                planeHeight={graph.planeHeight}
                planeWidth={graph.planeWidth}
                readonly={route.state.state !== 'ready' || connectivityStatus !== 'ready' || validating || saving}
                uniquePositionCount={graph.uniquePositionCount}
                onNode={selectNode}
              />
            </RouteRegion>
            <RouteRegion className={styles['legendRegion'] ?? ''} data-region="talent_legend"><TalentLegend /></RouteRegion>
            <RouteRegion className={styles['actionsRegion'] ?? ''} data-region="talent_actions"><TalentActionBar items={actions} /></RouteRegion>
            <TalentTemplateNameSheet
              visible={nameSheetOpen}
              value={templateTitle}
              saving={saving}
              onChange={setTemplateTitle}
              onClose={() => {
                if (!saving) setNameSheetOpen(false)
              }}
              onConfirm={() => void saveImportTemplate()}
            />
            <TalentTemplateImportSheet
              visible={importSheet !== 'closed'}
              activeTab={importSheet === 'community' ? 'community' : 'saved'}
              savedItems={savedImportItems}
              communityWinner={communityWinnerView}
              loading={loadingSavedTemplates}
              importing={importingTemplate}
              onTabChange={setImportSheet}
              onClose={() => {
                if (!importingTemplate) setImportSheet('closed')
              }}
              onImportSaved={(templateId) => void importSavedTemplate(templateId)}
              onImportCommunity={() => void importCommunityWinner()}
            />
          </View>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
