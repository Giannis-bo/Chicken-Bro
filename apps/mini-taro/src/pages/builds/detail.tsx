import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { taroStorage, wowApi } from '@wow-mini/api-client'
import {
  AppShell,
  GearActionRow,
  GearEnhancementBar,
  GearProfessionSelector,
  GearReadinessOverview,
  GearSlotWorkbench,
  GearSpecializationSelector,
  GearStatusDeck,
  PageFrame,
  StatusVisual,
  type GearActionItem,
  type GearProfessionItem,
  type GearSpecializationItem,
  type GearStatusItem,
} from '@wow-mini/design-system'
import {
  storageKey,
  type BuildTemplate,
  type BuildsDetailPayload,
  type BuildsHomePayload,
  type GearItemReference,
  type GearStatsPayload,
  type RouteDataState,
  type TalentImportPayload,
  type WebsimGearPayload,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  type SpecSelection,
} from '../_shared/build-context'
import {
  goBack,
  navigateTo,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  gearCandidates,
  gearEnhancementGroups,
  gearEnhancementOptions,
  gearReadiness,
  gearSlots,
  gearStatusDeck,
  templateGearItems,
} from './gear-detail-model'
import styles from './gear-detail.module.scss'

interface GearPagePayload {
  home: BuildsHomePayload
  selection: SpecSelection
  detail: BuildsDetailPayload
  gear: WebsimGearPayload
  talentImport: TalentImportPayload
  templates: readonly BuildTemplate[]
}

interface StatsState {
  loading: boolean
  payload?: GearStatsPayload
  error?: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseSavedTemplate(template: BuildTemplate | undefined): Readonly<Record<string, GearItemReference>> | null {
  if (!template) return null
  try {
    const parsed: unknown = JSON.parse(template.rawString)
    if (!isRecord(parsed)) return null
    const result: Record<string, GearItemReference> = {}
    for (const [slot, item] of Object.entries(parsed)) {
      if (isRecord(item) && (item['itemId'] || item['id'])) result[slot] = item as GearItemReference
    }
    return Object.keys(result).length ? result : null
  } catch {
    return null
  }
}

function routeReason(state: RouteDataState<unknown>): string {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  return ''
}

export default function GearDetailPage() {
  const router = useRouter()
  const queryMode = router.params['query'] || 'talents'
  const [selectedSpecId, setSelectedSpecId] = useState(safeDecode(router.params['spec']) || defaultSpecId)
  const [equipped, setEquipped] = useState<Readonly<Record<string, GearItemReference>>>({})
  const [selectedSlot, setSelectedSlot] = useState('')
  const [candidateOpen, setCandidateOpen] = useState(false)
  const [candidates, setCandidates] = useState<readonly GearItemReference[]>([])
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [enhancements, setEnhancements] = useState<Readonly<Record<string, string>>>({})
  const [stats, setStats] = useState<StatsState>({ loading: false })
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [workbenchNotice, setWorkbenchNotice] = useState('')
  const selectionChanged = useRef(false)
  const candidateRequestId = useRef(0)

  useEffect(() => {
    if (queryMode === 'gear') return
    void Taro.redirectTo({
      url: `/pages/builds/talent-simulator?spec=${encodeURIComponent(selectedSpecId)}`,
    })
  }, [queryMode, selectedSpecId])

  const route = useAsyncRoute<GearPagePayload>(async () => {
    const homeResult = await wowApi.builds.home()
    const selection = findSpecSelection(homeResult.payload, selectedSpecId)
    if (!selection) throw new Error('没有可用的职业专精映射')
    const request = { classKey: selection.classKey, specKey: selection.specKey }
    const [detailResult, gearResult, importResult, templateResult] = await Promise.all([
      wowApi.builds.detail(selection.specId),
      wowApi.websim.gear({ ...request, compact: true }),
      wowApi.websim.talentImport(request),
      wowApi.templates.fetch('gear'),
    ])
    const errors = [
      homeResult.error,
      detailResult.error,
      gearResult.error,
      importResult.error,
    ].filter(Boolean)
    return {
      payload: {
        home: homeResult.payload,
        selection,
        detail: detailResult.payload,
        gear: gearResult.payload,
        talentImport: importResult.payload,
        templates: templateResult.payload.templates,
      },
      fromFallback: homeResult.fromFallback
        || detailResult.fromFallback
        || gearResult.fromFallback
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
    const initialEquipped = route.data.gear.equippedSet
    setEquipped(initialEquipped)
    candidateRequestId.current += 1
    setSelectedSlot('')
    setCandidateOpen(false)
    setCandidates([])
    setEnhancements({})
    setStats({ loading: false, payload: route.data.gear.statSnapshot })
    setDirty(false)
  }, [route.data])

  useEffect(() => {
    if (!workbenchNotice) return undefined
    const timeout = setTimeout(() => setWorkbenchNotice(''), 1800)
    return () => clearTimeout(timeout)
  }, [workbenchNotice])

  const data = route.data
  const initialLoading = route.state.state === 'loading' && !data
  const selectedClass = data?.selection.classItem
  const classItems: readonly GearProfessionItem[] = selectedClass ? [{
    id: data?.selection.specId || selectedClass.websimClassKey || selectedClass.name,
    label: selectedClass.name,
    selected: true,
    ...(selectedClass.iconUrl ? { iconUrl: selectedClass.iconUrl } : {}),
  }] : []
  const specItems: readonly GearSpecializationItem[] = (data?.selection.classItem.specializations ?? []).map((spec) => ({
    id: spec.id || spec.specId || '',
    label: spec.specName || spec.title || spec.name,
  })).filter((item) => item.id)
  const selectedSpecIndex = Math.max(0, specItems.findIndex((item) => item.id === data?.selection.specId))
  const selectedSpecLabel = data?.selection.spec.specName || data?.selection.spec.title || data?.selection.spec.name || ''

  const slotViews = gearSlots(data?.gear, equipped, selectedSlot)
  const candidateViews = gearCandidates(candidates)
  const selectedCandidate = equipped[selectedSlot]
  const readiness = gearReadiness(equipped, stats.payload, route.state.state)
  const enhancementGroups = gearEnhancementGroups(selectedCandidate, enhancements, selectedSlot).map((group) => {
    const compatibleSlotCount = slotViews.filter((slot) => gearEnhancementOptions(equipped[slot.slot], enhancements, slot.slot)
      .some((option) => option.kind === group.id)).length
    const configuredCount = Object.keys(enhancements)
      .filter((key) => key.endsWith(`:${group.id}`)).length
    return {
      ...group,
      optionCount: compatibleSlotCount,
      value: configuredCount
        ? `已配置 ${configuredCount} 件`
        : compatibleSlotCount
          ? `${compatibleSlotCount} 个槽位可用`
          : '暂无可用',
      state: configuredCount ? 'ready' as const : compatibleSlotCount ? 'empty' as const : 'blocked' as const,
    }
  })
  const enhancementOptions = gearEnhancementOptions(selectedCandidate, enhancements, selectedSlot)
  const selectedSlotLabel = slotViews.find((slot) => slot.slot === selectedSlot)?.label ?? ''
  const currentReason = stats.error || routeReason(route.state)
  const statusItems = gearStatusDeck(data?.gear, readiness, stats.payload, route.state.state, currentReason)
  const importReady = data?.talentImport.status === 'verified' && Boolean(data.talentImport.importCode)
  const statsReady = Boolean(stats.payload && stats.payload.statStatus !== 'blocked' && !dirty)
  const communityTemplate = data?.gear.communityTemplates.find((template) => Boolean(templateGearItems(template)))
  const savedTemplate = data?.templates.find((template) => Boolean(parseSavedTemplate(template)))
  const importAvailable = Boolean(communityTemplate || savedTemplate)

  const chooseSlot = async (slot: { slot: string }) => {
    if (selectedSlot === slot.slot && candidateOpen) {
      candidateRequestId.current += 1
      setCandidateOpen(false)
      setCandidates([])
      setCandidateLoading(false)
      return
    }
    const requestId = candidateRequestId.current + 1
    candidateRequestId.current = requestId
    setSelectedSlot(slot.slot)
    setCandidateOpen(true)
    const local = data?.gear.replacementCandidates.find((group) => group.slot === slot.slot)
    setCandidates([])
    if (!data || route.state.state !== 'ready') {
      setCandidates(local?.items ?? [])
      setCandidateLoading(false)
      return
    }
    setCandidateLoading(true)
    try {
      const result = await wowApi.websim.gear({
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        compact: false,
        mode: 'slot',
        slot: slot.slot,
      })
      if (candidateRequestId.current !== requestId) return
      const group = result.fromFallback
        ? local
        : result.payload.replacementCandidates.find((item) => item.slot === slot.slot)
      setCandidates(group?.items ?? [])
      if (result.fromFallback) setWorkbenchNotice('网络暂不可用，显示当前槽位的本地候选')
    } catch {
      if (candidateRequestId.current !== requestId) return
      setCandidates(local?.items ?? [])
      setWorkbenchNotice('候选加载失败，已回退当前槽位的本地数据')
    } finally {
      if (candidateRequestId.current === requestId) setCandidateLoading(false)
    }
  }

  const chooseCandidate = (id: string) => {
    const index = candidateViews.findIndex((candidate) => candidate.id === id)
    const item = candidates[index]
    if (!item || !selectedSlot) return
    setEquipped((current) => ({ ...current, [selectedSlot]: item }))
    setEnhancements((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${selectedSlot}:`))))
    setStats({ loading: false })
    setDirty(true)
  }

  const chooseEnhancement = (item: { id: string; kind: string }, slot = selectedSlot) => {
    if (!slot) return
    setEnhancements((current) => ({ ...current, [`${slot}:${item.kind}`]: item.id }))
    setStats({ loading: false })
    setDirty(true)
  }

  const openEnhancementGroup = async (item: { id: 'socket' | 'enchant' | 'embellishment'; label: string }) => {
    const compatibleSlots = slotViews.flatMap((slot) => {
      const options = gearEnhancementOptions(equipped[slot.slot], enhancements, slot.slot)
        .filter((option) => option.kind === item.id)
      return options.length ? [{ slot: slot.slot, label: slot.label, options }] : []
    })
    if (!compatibleSlots.length) {
      await Taro.showToast({ title: `已选装备中没有可用${item.label}`, icon: 'none' })
      return
    }
    try {
      const target = compatibleSlots.find((entry) => entry.slot === selectedSlot) ?? compatibleSlots[0]
      if (!target) return
      setSelectedSlot(target.slot)
      setCandidateOpen(false)
      for (let offset = 0; offset < target.options.length; offset += 5) {
        const pageOptions = target.options.slice(offset, offset + 5)
        const hasMore = offset + pageOptions.length < target.options.length
        const choice = await Taro.showActionSheet({
          itemList: [...pageOptions.map((option) => option.label), ...(hasMore ? ['更多选项…'] : [])],
        })
        if (hasMore && choice.tapIndex === pageOptions.length) continue
        const selected = pageOptions[choice.tapIndex]
        if (selected) chooseEnhancement(selected, target.slot)
        return
      }
    } catch {
      // Closing the action sheet is a normal no-op.
    }
  }

  const validateStats = async () => {
    if (!data || !readiness.selectedCount) return
    if (!importReady) {
      setStats({ loading: false, error: '缺少后端已验证的天赋导入码，属性校验保持受限。' })
      return
    }
    setStats({ loading: true })
    const result = await wowApi.websim.gearStats({
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      talents: data.talentImport.importCode,
      gearBySlot: equipped,
      enhancementBySlot: enhancements,
      scenarioKey: 'single',
      metadata: { source: 'taro_gear_detail' },
    })
    setStats(result.fromFallback
      ? { loading: false, error: result.error || '属性校验不可用' }
      : { loading: false, payload: result.payload })
    if (!result.fromFallback && result.payload.statStatus !== 'blocked') setDirty(false)
  }

  const saveTemplate = async () => {
    if (!data || !readiness.selectedCount) return
    setSaving(true)
    try {
      const result = await wowApi.templates.upsert({
        type: 'gear',
        title: `${data.selection.label} · 装备`,
        classKey: data.selection.classKey,
        className: data.selection.classItem.name,
        specKey: data.selection.specKey,
        specName: data.selection.spec.specName || data.selection.spec.name,
        rawString: JSON.stringify(equipped),
        status: readiness.readyCount === readiness.requiredCount && statsReady ? 'complete' : 'partial',
        source: '装备工作台',
        metadata: { gearBySlot: equipped, enhancementBySlot: enhancements, statSnapshot: stats.payload ?? {} },
      })
      await Taro.showToast({ title: result.payload.template ? '装备模板已保存' : '保存失败', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  const importTemplate = () => {
    const imported = communityTemplate
      ? templateGearItems(communityTemplate)
      : parseSavedTemplate(savedTemplate)
    if (!imported) {
      void Taro.showToast({ title: '没有可导入的真实装备模板', icon: 'none' })
      return
    }
    const firstSlot = data?.gear.slots.find((slot) => imported[slot.slot])?.slot
      ?? Object.keys(imported)[0]
      ?? ''
    const group = data?.gear.replacementCandidates.find((item) => item.slot === firstSlot)
    setEquipped(imported)
    setSelectedSlot(firstSlot)
    setCandidateOpen(false)
    setCandidates(group?.items ?? [])
    setEnhancements({})
    setStats({ loading: false })
    setDirty(true)
    setWorkbenchNotice(communityTemplate ? '已导入来源模板' : '已导入已保存模板')
  }

  const reset = () => {
    const initial = data?.gear.equippedSet ?? {}
    const firstSlot = data?.gear.slots[0]?.slot ?? ''
    const group = data?.gear.replacementCandidates.find((item) => item.slot === firstSlot)
    setEquipped(initial)
    setSelectedSlot(firstSlot)
    setCandidateOpen(false)
    setCandidates(group?.items ?? [])
    setEnhancements({})
    setStats(data ? { loading: false, payload: data.gear.statSnapshot } : { loading: false })
    setDirty(false)
  }

  const handoffToSimc = () => {
    if (!data || !statsReady) return
    taroStorage.set(storageKey('simc.buildContext'), {
      specId: data.selection.specId,
      className: data.selection.classItem.name,
      specName: data.selection.spec.specName || data.selection.spec.name,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      gearBySlot: equipped,
      enhancementBySlot: enhancements,
      statSnapshot: stats.payload,
      source: 'taro_gear_detail',
    })
    navigateTo('/pages/simulator/simc', {
      from: 'builds',
      spec: data.selection.specId,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
    })
  }

  const primaryLabel = statsReady
    ? '带入 SimC'
    : !readiness.selectedCount
      ? '选择装备后开始配置'
      : !importReady
        ? '天赋编码不可用'
        : stats.loading
          ? '正在校验配置'
          : '校验当前配置'
  const primaryDisabled = !data || !readiness.selectedCount || !importReady || stats.loading

  const actions: readonly GearActionItem[] = route.state.state === 'error' && !data
    ? [
        { id: 'save', label: '重试', tone: 'gold', onClick: () => void route.load() },
        { id: 'import', label: '导入', tone: 'blue', disabled: true, onClick: () => undefined },
        { id: 'reset', label: '重置', tone: 'metal', disabled: true, onClick: () => undefined },
      ]
    : [
        { id: 'save', label: '保存模板', tone: 'gold', disabled: !readiness.selectedCount, loading: saving, onClick: () => void saveTemplate() },
        { id: 'import', label: '导入', tone: 'blue', disabled: !importAvailable, onClick: importTemplate },
        { id: 'reset', label: '重置', tone: 'metal', disabled: !data || (!dirty && !readiness.selectedCount), onClick: reset },
      ]

  const handleStatusAction = (item: GearStatusItem) => {
    if (item.id === 'catalog') {
      void route.load()
      return
    }
    if (item.id === 'selection') {
      const first = slotViews[0]
      if (first) void chooseSlot(first)
      return
    }
    if (item.id === 'validation') {
      if (importReady) void validateStats()
      else navigateTo('/pages/builds/talent-simulator', { spec: selectedSpecId })
      return
    }
    void Taro.showToast({ title: data?.gear.dataStatus === 'verified' ? '来源证据已由后端校验' : '来源证据尚不完整', icon: 'none' })
  }

  if (queryMode !== 'gear') {
    return <AppShell><PageFrame title="正在跳转天赋模拟"><StatusVisual state="loading" /></PageFrame></AppShell>
  }

  return (
    <AppShell
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.gear-detail-surface"
    >
      <View className={styles['pageFrame'] ?? ''} data-route-state={route.state.state} data-target-region-count="9">
        <PageFrame
          backRegion="header_nav.back-control"
          region="header_nav"
          title="装备详情"
          variant="gear-detail"
          onBack={() => goBack('/pages/builds/builds')}
        >
          <View className={styles['surface'] ?? ''} data-region="page_frame">
            {candidateOpen ? (
              <View
                aria-label="关闭装备候选"
                className={styles['candidateDismissLayer'] ?? ''}
                data-action-id="dismiss-candidates"
                role="button"
                onClick={() => {
                  candidateRequestId.current += 1
                  setCandidateOpen(false)
                  setCandidates([])
                  setCandidateLoading(false)
                }}
              />
            ) : null}
            <View className={styles['professionRegion'] ?? ''}>
              <GearProfessionSelector items={classItems} loading={initialLoading} />
            </View>
            <View className={styles['specializationRegion'] ?? ''}>
              <GearSpecializationSelector
                items={specItems}
                loading={initialLoading}
                selectedIndex={selectedSpecIndex}
                value={selectedSpecLabel}
                onSelect={(item) => setSelectedSpecId(item.id)}
              />
            </View>
            <View className={styles['readinessRegion'] ?? ''}>
              <GearReadinessOverview {...readiness} />
            </View>
            <View className={styles['enhancementRegion'] ?? ''}>
              <GearEnhancementBar items={enhancementGroups} onSelect={(item) => void openEnhancementGroup(item)} />
            </View>
            <View className={styles['workbenchRegion'] ?? ''}>
              <GearSlotWorkbench
                candidateOpen={candidateOpen}
                candidateLoading={candidateLoading}
                candidates={candidateViews}
                enhancements={enhancementOptions}
                notice={workbenchNotice}
                primaryDisabled={primaryDisabled}
                primaryLabel={primaryLabel}
                selectedSlot={selectedSlot}
                selectedSlotLabel={selectedSlotLabel}
                slots={slotViews}
                onCandidate={(item) => chooseCandidate(item.id)}
                onClose={() => {
                  candidateRequestId.current += 1
                  setCandidateOpen(false)
                  setCandidates([])
                  setCandidateLoading(false)
                }}
                onEnhancement={chooseEnhancement}
                onPrimary={statsReady ? handoffToSimc : () => void validateStats()}
                onSlot={(item) => void chooseSlot(item)}
              />
            </View>
            <View className={styles['actionsRegion'] ?? ''}><GearActionRow items={actions} /></View>
            <View className={styles['statusRegion'] ?? ''}><GearStatusDeck items={statusItems} onAction={handleStatusAction} /></View>
          </View>
        </PageFrame>
      </View>
    </AppShell>
  )
}
