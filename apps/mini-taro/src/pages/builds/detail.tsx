import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { taroStorage, wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  GearActionRow,
  GearEnhancementBar,
  GearProfessionSelector,
  GearReadinessOverview,
  GearSlotWorkbench,
  GearSpecializationSelector,
  GearStatusDeck,
  type GearActionItem,
  type GearProfessionItem,
  type GearSpecializationItem,
  type GearStatusItem,
} from '@wow-mini/design-system/components/GearDetailComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { StatusVisual } from '@wow-mini/design-system/components/StatusVisual'
import {
  storageKey,
  gearEnhancementsFromResolvedSnapshot,
  serializeGearSelectionIntent,
  type BuildTemplate,
  type BuildsDetailPayload,
  type BuildsHomePayload,
  type GearItemReference,
  type GearEnhancementSelection,
  type GearResolvedSnapshot,
  type GearSelectionIntent,
  type GearStatSnapshotPayload,
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
import { rememberBuildsHomeSpec } from '../_shared/build-context-storage'
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
import { GearRequestFence } from './gear-request-fence'
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
  payload?: GearStatsPayload | GearStatSnapshotPayload
  error?: string
}

interface CanonicalGearState {
  loading: boolean
  intent?: GearSelectionIntent
  snapshot?: GearResolvedSnapshot
  error?: string
}

type ResolveSelectionResult =
  | { status: 'resolved'; intent: GearSelectionIntent; snapshot: GearResolvedSnapshot }
  | { status: 'failed' }
  | { status: 'stale' }

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

function emptyEnhancementSelection(): GearEnhancementSelection {
  return {
    gemOptionIds: [],
    enchantOptionId: '',
    embellishmentOptionId: '',
    craftedOptionId: '',
    catalystOptionId: '',
  }
}

function importedGearBySlot(value: unknown): Readonly<Record<string, GearItemReference>> | null {
  if (!isRecord(value)) return null
  const result: Record<string, GearItemReference> = {}
  for (const [slot, item] of Object.entries(value)) {
    if (isRecord(item) && (item['itemId'] || item['id'])) result[slot] = item as GearItemReference
  }
  return Object.keys(result).length ? result : null
}

function envelopeMessage(problems: readonly Readonly<Record<string, unknown>>[], fallback: string): string {
  const first = problems[0]
  return String(first?.['title'] || first?.['detail'] || first?.['code'] || fallback)
}

function routeReason(state: RouteDataState<unknown>): string {
  if (state.state === 'error') return state.error
  if (state.state === 'blocked') return state.reason
  if (state.state === 'stale') return state.staleReason
  return ''
}

async function chooseActionSheetEntry<T>(
  items: readonly T[],
  labelFor: (item: T) => string,
): Promise<T | null> {
  for (let offset = 0; offset < items.length; offset += 5) {
    const pageItems = items.slice(offset, offset + 5)
    const hasMore = offset + pageItems.length < items.length
    try {
      const choice = await Taro.showActionSheet({
        itemList: [...pageItems.map(labelFor), ...(hasMore ? ['更多选项…'] : [])],
      })
      if (hasMore && choice.tapIndex === pageItems.length) continue
      return pageItems[choice.tapIndex] ?? null
    } catch {
      return null
    }
  }
  return null
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
  const [enhancements, setEnhancements] = useState<Readonly<Record<string, GearEnhancementSelection>>>({})
  const [canonical, setCanonical] = useState<CanonicalGearState>({ loading: false })
  const [stats, setStats] = useState<StatsState>({ loading: false })
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [workbenchNotice, setWorkbenchNotice] = useState('')
  const selectionChanged = useRef(false)
  const candidateRequestId = useRef(0)
  const requestFence = useRef(new GearRequestFence())

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
      wowApi.websim.gear({ ...request, compact: true, mode: 'initial' }),
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
  }, { fallbackPolicy: 'blocked' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    requestFence.current.replaceDraft()
    void route.load()
  }, [selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    requestFence.current.replaceDraft()
    const initialEquipped = route.data.gear.equippedSet
    setEquipped(initialEquipped)
    candidateRequestId.current += 1
    setSelectedSlot('')
    setCandidateOpen(false)
    setCandidates([])
    setEnhancements({})
    setCanonical({ loading: false })
    setStats({ loading: false, payload: route.data.gear.statSnapshot })
    setDirty(false)
  }, [route.data])

  useEffect(() => {
    if (!workbenchNotice) return undefined
    const timeout = setTimeout(() => setWorkbenchNotice(''), 1800)
    return () => clearTimeout(timeout)
  }, [workbenchNotice])

  const data = route.data
  const resolvedClassKey = data?.selection.classKey
  const resolvedSpecId = data?.selection.specId
  useEffect(() => {
    if (!data?.selection || !resolvedClassKey || !resolvedSpecId) return
    rememberBuildsHomeSpec(data.selection)
  }, [resolvedClassKey, resolvedSpecId])

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
  const readinessAuthority = canonical.loading
    ? undefined
    : canonical.snapshot?.profileReadiness ?? (!dirty ? data?.gear.readiness : undefined)
  const readiness = gearReadiness(
    equipped,
    stats.payload,
    canonical.loading ? 'loading' : route.state.state,
    readinessAuthority,
  )
  const enhancementGroups = gearEnhancementGroups(selectedCandidate, enhancements, selectedSlot).map((group) => {
    const compatibleSlotCount = slotViews.filter((slot) => gearEnhancementOptions(equipped[slot.slot], enhancements, slot.slot)
      .some((option) => option.kind === group.id)).length
    const configuredCount = Object.values(enhancements).filter((selection) => {
      if (group.id === 'socket') return selection.gemOptionIds.length > 0
      if (group.id === 'enchant') return Boolean(selection.enchantOptionId)
      return Boolean(selection.embellishmentOptionId)
    }).length
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
  const statusItems = gearStatusDeck(
    data?.gear,
    readiness,
    stats.payload,
    route.state.state,
    routeReason(route.state),
    canonical.error || stats.error || '',
  )
  const importReady = data?.talentImport.status === 'verified' && Boolean(data.talentImport.importCode)
  const statsReady = Boolean(
    canonical.snapshot?.status === 'verified'
    && canonical.intent
    && stats.payload?.statStatus === 'verified'
    && !dirty,
  )
  const communityTemplate = data?.gear.communityTemplates.find((template) => Boolean(templateGearItems(template)))
  const savedTemplate = data?.templates.find((template) => Boolean(parseSavedTemplate(template)))
  const importAvailable = Boolean(communityTemplate || savedTemplate)

  const resolveSelection = async (
    nextEquipped: Readonly<Record<string, GearItemReference>>,
    nextEnhancements: Readonly<Record<string, GearEnhancementSelection>>,
  ): Promise<ResolveSelectionResult> => {
    if (!data) return { status: 'failed' }
    const intent = serializeGearSelectionIntent({
      ...(data.gear.resolverContext ? { resolverContext: data.gear.resolverContext } : {}),
      selection: data.selection,
      ...(data.gear.maxLevel ? { level: data.gear.maxLevel } : {}),
      gearBySlot: nextEquipped,
      enhancementBySlot: nextEnhancements,
    })
    if (!intent) {
      requestFence.current.beginResolve()
      setCanonical({ loading: false, error: '后端未提供完整装备校验上下文' })
      return { status: 'failed' }
    }
    setCanonical((current) => ({
      loading: true,
      ...(current.intent ? { intent: current.intent } : {}),
      ...(current.snapshot ? { snapshot: current.snapshot } : {}),
    }))
    const completion = await requestFence.current.runResolve(() => wowApi.websim.gearResolve(intent))
    if (completion.status === 'stale') return completion
    const result = completion.value
    if (result.fromFallback) {
      setCanonical({ loading: false, intent, error: result.error || '装备校验服务不可用' })
      return { status: 'failed' }
    }
    if (result.httpStatus === 409) {
      setCanonical({ loading: false, intent, error: '装备数据版本已更新，正在重新加载' })
      setWorkbenchNotice('装备数据已更新，请重新选择')
      void route.load()
      return { status: 'failed' }
    }
    const snapshot = result.payload.data
    if (result.httpStatus !== 200 || result.payload.status !== 'resolved' || snapshot.status !== 'verified') {
      setCanonical({
        loading: false,
        intent,
        snapshot,
        error: envelopeMessage(result.payload.problems, '当前装备组合未通过后端校验'),
      })
      return { status: 'failed' }
    }
    setCanonical({ loading: false, intent, snapshot })
    return { status: 'resolved', intent, snapshot }
  }

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
      if (result.fromFallback) setWorkbenchNotice('网络暂不可用，保留上次从后端加载的候选')
    } catch {
      if (candidateRequestId.current !== requestId) return
      setCandidates(local?.items ?? [])
      setWorkbenchNotice('候选加载失败，保留上次从后端加载的候选')
    } finally {
      if (candidateRequestId.current === requestId) setCandidateLoading(false)
    }
  }

  const chooseCandidate = async (id: string) => {
    const index = candidateViews.findIndex((candidate) => candidate.id === id)
    const item = candidates[index]
    const slot = selectedSlot
    if (!item || !slot) return
    const nextEquipped = { ...equipped, [slot]: item }
    const nextEnhancements = Object.fromEntries(Object.entries(enhancements).filter(([key]) => key !== slot))

    candidateRequestId.current += 1
    requestFence.current.replaceDraft()
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
    setEquipped(nextEquipped)
    setEnhancements(nextEnhancements)
    setStats({ loading: false })
    setDirty(true)
    await resolveSelection(nextEquipped, nextEnhancements)
  }

  const chooseEnhancement = async (item: { id: string; kind: string }, slot = selectedSlot) => {
    if (!slot) return
    const current = enhancements[slot] ?? emptyEnhancementSelection()
    const nextSelection: GearEnhancementSelection = item.kind === 'socket'
      ? { ...current, gemOptionIds: [item.id] }
      : item.kind === 'enchant'
        ? { ...current, enchantOptionId: item.id }
        : { ...current, embellishmentOptionId: item.id }
    const nextEnhancements = { ...enhancements, [slot]: nextSelection }
    const resolved = await resolveSelection(equipped, nextEnhancements)
    if (resolved.status !== 'resolved') return
    setEnhancements(nextEnhancements)
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
    const activeTarget = compatibleSlots.find((entry) => entry.slot === selectedSlot)
    const target = activeTarget ?? (compatibleSlots.length === 1
      ? compatibleSlots[0]
      : await chooseActionSheetEntry(compatibleSlots, (entry) => `${entry.label}（${entry.options.length} 项）`))
    if (!target) return
    setSelectedSlot(target.slot)
    setCandidateOpen(false)
    const selected = await chooseActionSheetEntry(target.options, (option) => option.label)
    if (selected) await chooseEnhancement(selected, target.slot)
  }

  const validateStats = async () => {
    if (!data || !readiness.selectedCount) return
    if (!importReady) {
      setStats({ loading: false, error: '缺少后端已验证的天赋导入码，属性校验保持受限。' })
      return
    }
    setStats({ loading: true })
    const resolved = await resolveSelection(equipped, enhancements)
    if (resolved.status === 'stale') return
    if (resolved.status === 'failed') {
      setStats({ loading: false, error: '当前装备组合未通过后端校验' })
      return
    }
    const requestToken = requestFence.current.beginStats()
    const startedAt = Date.now()
    for (let attempt = 0; attempt < 15 && Date.now() - startedAt < 45000; attempt += 1) {
      if (!requestFence.current.isStatsCurrent(requestToken)) return
      const result = await wowApi.websim.gearStatSnapshot({
        selectionIntent: resolved.intent,
        profileContext: {
          talents: data.talentImport.importCode,
          scenarioKey: 'single',
        },
        timeoutMs: Math.max(1, 45000 - (Date.now() - startedAt)),
      })
      if (!requestFence.current.isStatsCurrent(requestToken)) return
      if (result.fromFallback) {
        setStats({ loading: false, error: result.error || '属性快照服务不可用' })
        return
      }
      const payload = result.payload.data.statSnapshot
      if (result.httpStatus === 200 && result.payload.status === 'resolved' && payload?.statStatus === 'verified') {
        setStats({ loading: false, payload })
        setDirty(false)
        return
      }
      if (result.httpStatus !== 202 || result.payload.status !== 'pending') {
        setStats({ loading: false, error: envelopeMessage(result.payload.problems, '属性快照未通过后端校验') })
        return
      }
      const delay = Math.min(5000, Math.max(250, Number(result.payload.data.retryAfterMs) || 1500))
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
    if (requestFence.current.isStatsCurrent(requestToken)) {
      setStats({ loading: false, error: '属性快照等待超时' })
    }
  }

  const saveTemplate = async () => {
    if (!data || !readiness.selectedCount) return
    setSaving(true)
    try {
      const resolved = await resolveSelection(equipped, enhancements)
      if (resolved.status === 'stale') return
      if (resolved.status === 'failed') {
        await Taro.showToast({ title: '装备未通过后端校验，暂不能保存', icon: 'none' })
        return
      }
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
        metadata: {
          gearBySlot: equipped,
          enhancementBySlot: enhancements,
          selectionIntent: resolved.intent,
          resolvedGearSignature: resolved.snapshot.resolvedGearSignature ?? '',
          statSnapshot: statsReady ? stats.payload ?? {} : {},
        },
      })
      await Taro.showToast({ title: result.payload.template ? '装备模板已保存' : '保存失败', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  const importTemplate = async () => {
    const importToken = requestFence.current.beginImport()
    let imported: Readonly<Record<string, GearItemReference>> | null = null
    let importedSnapshot: GearResolvedSnapshot | undefined
    let importedIntent: GearSelectionIntent | undefined
    let importedEnhancements: Readonly<Record<string, GearEnhancementSelection>> = {}
    if (communityTemplate?.id && data) {
      const result = await wowApi.websim.communityTemplateImport({
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        templateId: communityTemplate.id,
        ...(data.gear.manifestRevision ? { expectedManifestRevision: data.gear.manifestRevision } : {}),
      })
      if (!requestFence.current.isImportCurrent(importToken)) return
      if (!result.fromFallback && result.httpStatus === 200 && result.payload.status === 'verified') {
        imported = importedGearBySlot(result.payload.data['importedGearBySlot'])
        importedSnapshot = result.payload.data.resolvedSnapshot
        if (imported && importedSnapshot) {
          importedEnhancements = gearEnhancementsFromResolvedSnapshot(importedSnapshot, imported) ?? {}
          importedIntent = serializeGearSelectionIntent({
            ...(data.gear.resolverContext ? { resolverContext: data.gear.resolverContext } : {}),
            selection: data.selection,
            ...(data.gear.maxLevel ? { level: data.gear.maxLevel } : {}),
            gearBySlot: imported,
            enhancementBySlot: importedEnhancements,
          }) ?? undefined
        }
        if (!imported || !importedSnapshot || !Object.keys(importedEnhancements).length || !importedIntent) {
          setWorkbenchNotice('社区模板返回的装备与校验快照不完整')
          return
        }
      } else {
        setWorkbenchNotice(result.fromFallback
          ? '社区模板导入服务不可用'
          : envelopeMessage(result.payload.problems, '社区模板未通过完整性校验'))
        return
      }
    } else {
      imported = parseSavedTemplate(savedTemplate)
    }
    if (!imported) {
      void Taro.showToast({ title: '没有可导入的真实装备模板', icon: 'none' })
      return
    }
    if (!requestFence.current.isImportCurrent(importToken)) return
    const firstSlot = data?.gear.slots.find((slot) => imported[slot.slot])?.slot
      ?? Object.keys(imported)[0]
      ?? ''
    const group = data?.gear.replacementCandidates.find((item) => item.slot === firstSlot)
    requestFence.current.replaceDraft()
    candidateRequestId.current += 1
    setEquipped(imported)
    setSelectedSlot(firstSlot)
    setCandidateOpen(false)
    setCandidates(group?.items ?? [])
    setEnhancements(importedEnhancements)
    setStats({ loading: false })
    setDirty(true)
    if (importedSnapshot?.status === 'verified' && importedIntent) {
      setCanonical({ loading: false, intent: importedIntent, snapshot: importedSnapshot })
    } else {
      void resolveSelection(imported, importedEnhancements)
    }
    setWorkbenchNotice(communityTemplate ? '已原子导入来源模板' : '已导入已保存模板并重新校验')
  }

  const reset = () => {
    const initial = data?.gear.equippedSet ?? {}
    const firstSlot = data?.gear.slots[0]?.slot ?? ''
    const group = data?.gear.replacementCandidates.find((item) => item.slot === firstSlot)
    requestFence.current.replaceDraft()
    candidateRequestId.current += 1
    setEquipped(initial)
    setSelectedSlot(firstSlot)
    setCandidateOpen(false)
    setCandidates(group?.items ?? [])
    setEnhancements({})
    setCanonical({ loading: false })
    setStats(data ? { loading: false, payload: data.gear.statSnapshot } : { loading: false })
    setDirty(false)
  }

  const handoffToSimc = () => {
    if (!data || !statsReady || !canonical.intent || !canonical.snapshot) return
    taroStorage.set(storageKey('simc.buildContext'), {
      specId: data.selection.specId,
      className: data.selection.classItem.name,
      specName: data.selection.spec.specName || data.selection.spec.name,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      gearBySlot: equipped,
      enhancementBySlot: enhancements,
      selectionIntent: canonical.intent,
      resolvedGearSignature: canonical.snapshot.resolvedGearSignature,
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
        : stats.loading || canonical.loading
          ? '正在校验配置'
          : '校验当前配置'
  const primaryDisabled = !data || !readiness.selectedCount || !importReady || stats.loading || canonical.loading

  const actions: readonly GearActionItem[] = route.state.state === 'error' && !data
    ? [
        { id: 'save', label: '重试', tone: 'gold', onClick: () => void route.load() },
        { id: 'import', label: '导入', tone: 'blue', disabled: true, onClick: () => undefined },
        { id: 'reset', label: '重置', tone: 'metal', disabled: true, onClick: () => undefined },
      ]
    : [
        { id: 'save', label: '保存模板', tone: 'gold', disabled: !readiness.selectedCount, loading: saving, onClick: () => void saveTemplate() },
        { id: 'import', label: '导入', tone: 'blue', disabled: !importAvailable, onClick: () => void importTemplate() },
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
    return <AppShell><PageFrame title="正在跳转天赋模拟" variant="gear-detail"><StatusVisual state="loading" /></PageFrame></AppShell>
  }

  return (
    <AppShell
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.gear-detail-surface"
    >
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={route.state.state} targetRegionCount={9} width="full">
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
                data-owner="gear-candidate-page-dismiss"
                role="button"
                onClick={() => {
                  candidateRequestId.current += 1
                  setCandidateOpen(false)
                  setCandidates([])
                  setCandidateLoading(false)
                }}
              />
            ) : null}
            <RouteRegion className={styles['professionRegion'] ?? ''} data-region="profession_selector">
              <GearProfessionSelector items={classItems} loading={initialLoading} />
            </RouteRegion>
            <RouteRegion className={styles['specializationRegion'] ?? ''} data-region="specialization_selector">
              <GearSpecializationSelector
                items={specItems}
                loading={initialLoading}
                selectedIndex={selectedSpecIndex}
                value={selectedSpecLabel}
                onSelect={(item) => setSelectedSpecId(item.id)}
              />
            </RouteRegion>
            <RouteRegion className={styles['readinessRegion'] ?? ''} data-region="readiness_summary">
              <GearReadinessOverview {...readiness} />
            </RouteRegion>
            <RouteRegion className={styles['enhancementRegion'] ?? ''} data-region="enhancement_summary">
              <GearEnhancementBar items={enhancementGroups} onSelect={(item) => void openEnhancementGroup(item)} />
            </RouteRegion>
            <RouteRegion className={styles['workbenchRegion'] ?? ''} data-region="gear_workbench">
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
            </RouteRegion>
            <RouteRegion className={styles['actionsRegion'] ?? ''} data-region="gear_actions"><GearActionRow items={actions} /></RouteRegion>
            <RouteRegion className={styles['statusRegion'] ?? ''} data-region="gear_status"><GearStatusDeck items={statusItems} onAction={handleStatusAction} /></RouteRegion>
          </View>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
