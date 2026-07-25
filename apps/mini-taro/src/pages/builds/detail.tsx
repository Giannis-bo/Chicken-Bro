import Taro, { useRouter } from '@tarojs/taro'
import { View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  GearActionRow,
  GearEnhancementBar,
  GearLoadoutSummary,
  GearProfessionSelector,
  GearSlotWorkbench,
  GearSpecializationSelector,
  type GearActionItem,
  type GearProfessionItem,
  type GearSpecializationItem,
} from '@wow-mini/design-system/components/GearDetailComponents'
import {
  GearCandidateEditorSheet,
  GearEnhancementEditorSheet,
} from '@wow-mini/design-system/components/GearEditorSheets'
import {
  GearTemplateImportSheet,
  type GearTemplateCommunityImportItem,
  type TalentTemplateSavedImportItem,
} from '@wow-mini/design-system/components/TalentSimulatorComponents'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { StatusVisual } from '@wow-mini/design-system/components/StatusVisual'
import {
  gearEnhancementsFromResolvedSnapshot,
  gearItemStaticStatsFromResolvedSnapshot,
  serializeGearSelectionIntent,
  type BuildTemplate,
  type BuildsDetailPayload,
  type BuildsHomePayload,
  type CommunityTemplateReference,
  type GearItemReference,
  type GearEnhancementSelection,
  type GearResolvedSnapshot,
  type GearSelectionIntent,
  type GearStatSnapshotPayload,
  type GearStatsPayload,
  type TalentImportPayload,
  type WebsimGearPayload,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  resolveBuildsHomeLaunch,
  type SpecSelection,
} from '../_shared/build-context'
import { rememberBuildsHomeSpec, selectBuildsHomeClass } from '../_shared/build-context-storage'
import {
  goBack,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  candidateDraftCanApply,
  createCandidateDraft,
  emptyEnhancementSelection,
  isEnhancementKindConfigured,
  materializeCandidateDraft,
  packedEnhancementSelection,
  selectCandidateVariant,
  setGemAtSocket,
  setSingleEnhancement,
  type GearCandidateDraft,
} from './gear-detail-editor-model'
import {
  enhancementDraftSelections,
  isProfileIncompleteOnlySnapshot,
  resolvedSlotIdentity,
  selectEnhancementDraftSlot as selectEnhancementDraftSlotModel,
  transitionGearEditorCommit,
  updateEnhancementDraftSelection,
  type GearEditorCommitState,
  type GearEnhancementDraft,
  type GearEnhancementKind,
} from './gear-detail-editor-commit-model'
import {
  gearCandidates,
  gearEnhancementGroups,
  gearEnhancementOptions,
  gearEnhancementSocketCount,
  gearItemIconUrl,
  gearItemLevel,
  gearItemName,
  hydrateCompactSlotGroup,
  gearReadiness,
  gearSlots,
  prepareHydratedEnhancementDraft,
} from './gear-detail-model'
import { GearRequestFence } from './gear-request-fence'
import {
  communityGearTemplateOptions,
  formatGearTemplateUpdatedAt,
  savedGearTemplateOptions,
  serializeGearTemplateDraft,
  type GearTemplateDraft,
} from './gear-template-import-model'
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
}

interface CanonicalGearState {
  loading: boolean
  intent?: GearSelectionIntent
  snapshot?: GearResolvedSnapshot
  error?: string
}

type ResolveSelectionResult =
  | { status: 'resolved'; intent: GearSelectionIntent; snapshot: GearResolvedSnapshot }
  | { status: 'slot_resolved'; intent: GearSelectionIntent; snapshot: GearResolvedSnapshot }
  | { status: 'failed' }
  | { status: 'conflict' }
  | { status: 'stale' }

type GearImportSelection =
  | { kind: 'community'; template: CommunityTemplateReference; label: string }
  | { kind: 'saved'; draft: GearTemplateDraft; label: string }

type SlotHydrationResult =
  | { readonly status: 'current'; readonly items: readonly GearItemReference[] }
  | { readonly status: 'failed' | 'stale' }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
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

export default function GearDetailPage() {
  const router = useRouter()
  const queryMode = router.params['query'] || 'talents'
  const [selectedSpecId, setSelectedSpecId] = useState(safeDecode(router.params['spec']) || defaultSpecId)
  const [equipped, setEquipped] = useState<Readonly<Record<string, GearItemReference>>>({})
  const [selectedSlot, setSelectedSlot] = useState('')
  const [candidateOpen, setCandidateOpen] = useState(false)
  const [candidates, setCandidates] = useState<readonly GearItemReference[]>([])
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [candidateDraft, setCandidateDraft] = useState<GearCandidateDraft | null>(null)
  const [enhancements, setEnhancements] = useState<Readonly<Record<string, GearEnhancementSelection>>>({})
  const [enhancementDraft, setEnhancementDraft] = useState<GearEnhancementDraft | null>(null)
  const [enhancementLoading, setEnhancementLoading] = useState(false)
  const [canonical, setCanonical] = useState<CanonicalGearState>({ loading: false })
  const [stats, setStats] = useState<StatsState>({ loading: false })
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedTemplates, setSavedTemplates] = useState<readonly BuildTemplate[]>([])
  const [importSheet, setImportSheet] = useState<'closed' | 'saved' | 'community'>('closed')
  const [importingTemplate, setImportingTemplate] = useState(false)
  const [workbenchNotice, setWorkbenchNotice] = useState('')
  const selectionChanged = useRef(false)
  const candidateRequestId = useRef(0)
  const slotDetailCache = useRef(new Map<string, readonly GearItemReference[]>())
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
    candidateRequestId.current += 1
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
    setEnhancementLoading(false)
    slotDetailCache.current.clear()
    setCanonical({ loading: false })
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
    setCandidateLoading(false)
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setEnhancementLoading(false)
    slotDetailCache.current.clear()
    setEnhancements({})
    setCanonical({ loading: false })
    setStats({ loading: false, payload: route.data.gear.statSnapshot })
    setSavedTemplates(route.data.templates.filter((template) => template.type === 'gear'))
    setImportSheet('closed')
    setImportingTemplate(false)
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
  const classItems: readonly GearProfessionItem[] = (data?.home.classOptions ?? [])
    .filter((classItem) => Boolean(classItem.websimClassKey) && classItem.specializations.length > 0)
    .map((classItem) => ({
      id: classItem.websimClassKey,
      label: classItem.name,
      selected: classItem.websimClassKey === data?.selection.classKey,
      ...(classItem.iconUrl ? { iconUrl: classItem.iconUrl } : {}),
    }))
  const selectedClassIndex = Math.max(0, classItems.findIndex((item) => item.selected))
  const selectedClassLabel = classItems[selectedClassIndex]?.label ?? ''
  const specItems: readonly GearSpecializationItem[] = (data?.selection.classItem.specializations ?? []).map((spec) => ({
    id: spec.id || spec.specId || '',
    label: spec.specName || spec.title || spec.name,
    ...(spec.specIconUrl || spec.iconUrl ? { iconUrl: spec.specIconUrl || spec.iconUrl } : {}),
  })).filter((item) => item.id)
  const selectedSpecIndex = Math.max(0, specItems.findIndex((item) => item.id === data?.selection.specId))
  const selectedSpecLabel = data?.selection.spec.specName || data?.selection.spec.title || data?.selection.spec.name || ''

  const itemStaticStats = gearItemStaticStatsFromResolvedSnapshot(canonical.snapshot, equipped) ?? undefined
  const slotViews = gearSlots(data?.gear, equipped, selectedSlot, enhancements, itemStaticStats)
  const candidateViews = gearCandidates(candidates)
  const selectedCandidateIndex = candidateDraft ? candidates.indexOf(candidateDraft.candidate) : -1
  const selectedCandidateId = selectedCandidateIndex >= 0 ? candidateViews[selectedCandidateIndex]?.id ?? '' : ''
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
    const configuredCount = Object.values(enhancements).filter((selection) => (
      isEnhancementKindConfigured(selection, group.id)
    )).length
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
  const enhancementSelections = enhancementDraft
    ? enhancementDraftSelections(enhancementDraft)
    : enhancements
  const enhancementDraftOptions = enhancementDraft?.item
    ? gearEnhancementOptions(
        enhancementDraft.item,
        { [enhancementDraft.slot]: enhancementDraft.selection },
        enhancementDraft.slot,
      )
    : []
  const enhancementSocketCount = enhancementDraft?.item
    ? gearEnhancementSocketCount(enhancementDraft.item) ?? 0
    : 0
  const enhancementDraftItem = enhancementDraft?.item
  const enhancementDraftItemLevel = gearItemLevel(enhancementDraftItem)
  const enhancementDraftItemIconUrl = gearItemIconUrl(enhancementDraftItem)
  const enhancementEditorItem = enhancementDraftItem
    ? {
        label: gearItemName(enhancementDraftItem),
        levelLabel: enhancementDraftItemLevel === null ? '装等待校验' : `装等 ${Math.round(enhancementDraftItemLevel)}`,
        ...(enhancementDraftItemIconUrl ? { iconUrl: enhancementDraftItemIconUrl } : {}),
      }
    : undefined
  const enhancementCompatibleSlots = enhancementDraft
    ? slotViews.flatMap((slot) => {
        const item = equipped[slot.slot]
        const kind = enhancementDraft.requestedKind
        if (!item) return []
        const potentiallyCompatible = kind === 'socket'
          ? gearEnhancementSocketCount(item) !== 0
          : kind === 'enchant'
            ? item.modCapabilities?.['canEnchant'] !== false
            : item.modCapabilities?.['canEmbellish'] !== false
        if (!potentiallyCompatible) return []
        const selection = enhancementSelections[slot.slot] ?? emptyEnhancementSelection()
        const knownOptions = gearEnhancementOptions(item, { [slot.slot]: selection }, slot.slot)
          .filter((option) => option.kind === kind)
        const configured = isEnhancementKindConfigured(selection, kind)
        const itemLevel = gearItemLevel(item)
        const iconUrl = gearItemIconUrl(item)
        return [{
          slot: slot.slot,
          label: slot.label,
          item: {
            label: gearItemName(item),
            levelLabel: itemLevel === null ? '装等待校验' : `装等 ${Math.round(itemLevel)}`,
            ...(iconUrl ? { iconUrl } : {}),
          },
          summary: configured
            ? '草稿已配置'
            : knownOptions.length
              ? `${knownOptions.length} 项可选`
              : '选择后核验',
          selected: enhancementDraft.slot === slot.slot,
        }]
      })
    : []
  const selectedSlotLabel = slotViews.find((slot) => slot.slot === selectedSlot)?.label ?? ''
  const gearResolveState = canonical.loading
    ? 'resolving' as const
    : canonical.error
      ? 'error' as const
      : canonical.snapshot?.status === 'verified'
        ? 'verified' as const
        : 'idle' as const
  const resolvedIdentity = resolvedSlotIdentity(canonical.snapshot, selectedSlot)
  const resolvedSlotItemId = resolvedIdentity?.itemId ?? ''
  const resolvedSlotVariantKey = resolvedIdentity?.variantKey ?? ''
  const committedSlotVariantKey = String(equipped[selectedSlot]?.variantKey ?? '').trim()
  const statsReady = Boolean(
    canonical.snapshot?.status === 'verified'
    && canonical.intent
    && stats.payload?.statStatus === 'verified'
    && !dirty,
  )
  const communityTemplateOptions = communityGearTemplateOptions(data?.gear.communityTemplates ?? [])
  const savedTemplateOptions = savedGearTemplateOptions(savedTemplates, data?.selection.classKey ?? '', data?.selection.specKey ?? '')
  const importAvailable = Boolean(communityTemplateOptions.length || savedTemplateOptions.length)
  const savedImportItems: readonly TalentTemplateSavedImportItem[] = savedTemplateOptions.map((option) => ({
    id: option.template.id,
    title: option.label,
    detail: `更新：${formatGearTemplateUpdatedAt(option.template.updatedAt)}`,
  }))
  const communityImportItems: readonly GearTemplateCommunityImportItem[] = communityTemplateOptions.map((option) => {
    const template = option.template
    const player = template.playerName || template.name || template.title || '未提供'
    return {
      id: template.id || option.label,
      title: option.label,
      meta: [
        `玩家：${player}`,
        `服务器：${template.serverName || '未提供'}`,
        `区域：${template.region || '未提供'}`,
        typeof template.mplusScore === 'number' && template.mplusScore > 0
          ? `大秘境总分：${template.mplusScore}`
          : '大秘境总分：未提供',
        `更新：${formatGearTemplateUpdatedAt(template.updatedAt)}`,
      ],
      isStale: template.isStale === true || template.freshnessStatus === 'stale',
      importable: template.canApplyGear !== false,
    }
  })

  const selectProfession = (item: GearProfessionItem) => {
    if (!data || item.selected) return
    const nextContext = selectBuildsHomeClass(item.id)
    const launch = resolveBuildsHomeLaunch(data.home, nextContext)
    if (!launch || launch.selection.specId === data.selection.specId) return
    setSelectedSpecId(launch.selection.specId)
  }

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
      setWorkbenchNotice('后端未提供完整装备校验上下文')
      setCanonical({ loading: false, error: '后端未提供完整装备校验上下文' })
      return { status: 'failed' }
    }
    setCanonical((current) => ({
      loading: true,
      ...(current.intent ? { intent: current.intent } : {}),
      ...(current.snapshot ? { snapshot: current.snapshot } : {}),
    }))
    const resolveToken = requestFence.current.beginResolve()
    let result
    try {
      result = await wowApi.websim.gearResolve(intent)
    } catch {
      if (!requestFence.current.isResolveCurrent(resolveToken)) return { status: 'stale' }
      setWorkbenchNotice('装备校验网络不可用，草稿已保留')
      setCanonical({ loading: false, intent, error: '装备校验网络不可用' })
      return { status: 'failed' }
    }
    if (!requestFence.current.isResolveCurrent(resolveToken)) return { status: 'stale' }
    if (result.fromFallback) {
      setWorkbenchNotice(result.error || '装备校验服务不可用')
      setCanonical({ loading: false, intent, error: result.error || '装备校验服务不可用' })
      return { status: 'failed' }
    }
    if (result.httpStatus === 409) {
      const transition = transitionGearEditorCommit({
        equipped,
        enhancements,
        candidateDraft,
        enhancementDraft,
      }, { status: 'conflict' })
      candidateRequestId.current += 1
      setCandidateDraft(transition.state.candidateDraft)
      setEnhancementDraft(transition.state.enhancementDraft)
      setCandidateOpen(false)
      setCandidates([])
      setCandidateLoading(false)
      setEnhancementLoading(false)
      slotDetailCache.current.clear()
      setCanonical({ loading: false, intent, error: '装备数据版本已更新，正在重新加载' })
      setWorkbenchNotice('装备数据已更新，请重新选择')
      void route.load()
      return { status: 'conflict' }
    }
    const snapshot = result.payload.data
    if (
      result.httpStatus === 200
      && result.payload.status === 'blocked'
      && isProfileIncompleteOnlySnapshot(snapshot)
    ) {
      setCanonical({ loading: false, intent, snapshot })
      return { status: 'slot_resolved', intent, snapshot }
    }
    if (result.httpStatus !== 200 || result.payload.status !== 'resolved' || snapshot.status !== 'verified') {
      const error = envelopeMessage(result.payload.problems, '当前装备组合未通过后端校验')
      setWorkbenchNotice(error)
      setCanonical({
        loading: false,
        intent,
        snapshot,
        error,
      })
      return { status: 'failed' }
    }
    setCanonical({ loading: false, intent, snapshot })
    return { status: 'resolved', intent, snapshot }
  }

  const closeCandidateEditor = () => {
    candidateRequestId.current += 1
    requestFence.current.replaceDraft()
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
    setEnhancementLoading(false)
    setCanonical((current) => current.loading
      ? {
          loading: false,
          ...(current.intent ? { intent: current.intent } : {}),
          ...(current.snapshot ? { snapshot: current.snapshot } : {}),
        }
      : current)
  }

  const hydrateSlot = async (
    slot: string,
    requestId: number,
    publishCandidates: boolean,
  ): Promise<SlotHydrationResult> => {
    const cached = slotDetailCache.current.get(slot)
    if (cached) {
      if (candidateRequestId.current !== requestId) return { status: 'stale' }
      if (publishCandidates) setCandidates(cached)
      return { status: 'current', items: cached }
    }
    if (!data || route.state.state !== 'ready') {
      if (candidateRequestId.current === requestId) {
        setWorkbenchNotice('后端槽位详情尚未就绪')
      }
      return { status: 'failed' }
    }
    try {
      const result = await wowApi.websim.gear({
        classKey: data.selection.classKey,
        specKey: data.selection.specKey,
        compact: true,
        mode: 'slot',
        slot,
      })
      if (candidateRequestId.current !== requestId) return { status: 'stale' }
      if (result.fromFallback) {
        setWorkbenchNotice(result.error || '槽位详情服务不可用，未使用精简目录')
        return { status: 'failed' }
      }
      const group = result.payload.replacementCandidates.find((item) => item.slot === slot)
      if (!group) {
        setWorkbenchNotice('后端未返回当前槽位候选组')
        return { status: 'failed' }
      }
      const items = hydrateCompactSlotGroup(group)
      slotDetailCache.current.set(slot, items)
      if (publishCandidates) setCandidates(items)
      return { status: 'current', items }
    } catch {
      if (candidateRequestId.current !== requestId) return { status: 'stale' }
      setWorkbenchNotice('槽位详情加载失败，已确认装备保持不变')
      return { status: 'failed' }
    }
  }

  const chooseSlot = async (slot: { slot: string }) => {
    if (selectedSlot === slot.slot && candidateOpen) {
      closeCandidateEditor()
      return
    }
    requestFence.current.replaceDraft()
    setCanonical((current) => current.loading
      ? {
          loading: false,
          ...(current.intent ? { intent: current.intent } : {}),
          ...(current.snapshot ? { snapshot: current.snapshot } : {}),
        }
      : current)
    const requestId = candidateRequestId.current + 1
    candidateRequestId.current = requestId
    setSelectedSlot(slot.slot)
    setWorkbenchNotice('')
    setCandidateOpen(true)
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setEnhancementLoading(false)
    setCandidates([])
    setCandidateLoading(true)
    const hydrated = await hydrateSlot(slot.slot, requestId, true)
    if (candidateRequestId.current === requestId) {
      setCandidateLoading(false)
      if (hydrated.status === 'current' && !hydrated.items.length) {
        setWorkbenchNotice('当前槽位没有后端可校验候选')
      }
    }
  }

  const chooseCandidate = (id: string) => {
    if (canonical.loading) return
    const index = candidateViews.findIndex((candidate) => candidate.id === id)
    const item = candidates[index]
    const slot = selectedSlot
    if (!item || !slot) return
    setCandidateDraft(createCandidateDraft(slot, item))
  }

  const chooseCandidateVariant = (variantKey: string) => {
    if (canonical.loading) return
    setCandidateDraft((current) => current
      ? selectCandidateVariant(current, variantKey)
      : current)
  }

  const applyCandidateDraft = async () => {
    const draft = candidateDraft
    const item = draft && materializeCandidateDraft(draft)
    if (!draft || !item) return
    const commitState: GearEditorCommitState = {
      equipped,
      enhancements,
      candidateDraft,
      enhancementDraft,
    }
    const nextEquipped = { ...equipped, [draft.slot]: item }
    const nextEnhancements = Object.fromEntries(
      Object.entries(enhancements).filter(([slot]) => slot !== draft.slot),
    )
    const resolved = await resolveSelection(nextEquipped, nextEnhancements)
    if (resolved.status === 'conflict') return
    if (resolved.status !== 'resolved' && resolved.status !== 'slot_resolved') return
    const transition = transitionGearEditorCommit(commitState, {
      status: resolved.status,
      kind: 'candidate',
      slot: draft.slot,
      item,
      snapshot: resolved.snapshot,
    })
    if (!transition.committed) return
    setEquipped(transition.state.equipped)
    setEnhancements(transition.state.enhancements)
    setStats({ loading: false })
    setDirty(true)
    candidateRequestId.current += 1
    setCandidateDraft(transition.state.candidateDraft)
    setEnhancementDraft(transition.state.enhancementDraft)
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
  }

  const chooseEnhancement = (kind: 'enchant' | 'embellishment', optionId: string) => {
    setEnhancementDraft((current) => current
      ? updateEnhancementDraftSelection(current, setSingleEnhancement(current.selection, kind, optionId))
      : current)
  }

  const confirmEnhancementDraft = async () => {
    const draft = enhancementDraft
    if (!draft || !draft.item || draft.blockers.length) return
    const commitState: GearEditorCommitState = {
      equipped,
      enhancements,
      candidateDraft,
      enhancementDraft,
    }
    const nextEnhancements = enhancementDraftSelections(draft)
    const resolved = await resolveSelection(equipped, nextEnhancements)
    if (resolved.status === 'conflict') return
    if (resolved.status !== 'resolved') return
    const transition = transitionGearEditorCommit(commitState, {
      status: 'resolved',
      kind: 'enhancement',
      slot: draft.slot,
      snapshot: resolved.snapshot,
    })
    if (!transition.committed) {
      setWorkbenchNotice('后端校验结果缺少当前槽位强化，草稿已保留')
      return
    }
    setEquipped(transition.state.equipped)
    setEnhancements(transition.state.enhancements)
    setStats({ loading: false })
    setDirty(true)
    candidateRequestId.current += 1
    setCandidateDraft(transition.state.candidateDraft)
    setEnhancementDraft(transition.state.enhancementDraft)
    setEnhancementLoading(false)
  }

  const selectEnhancementDraftSlot = async (
    slot: string,
    initialDraft: GearEnhancementDraft | null = enhancementDraft,
  ) => {
    const committedItem = equipped[slot]
    if (!initialDraft || !committedItem) return
    const selectionBySlot = enhancementDraftSelections(initialDraft)
    const confirmed = selectionBySlot[slot] ?? emptyEnhancementSelection()
    const requestId = candidateRequestId.current + 1
    candidateRequestId.current = requestId
    setSelectedSlot(slot)
    const preparingDraft: GearEnhancementDraft = {
      slot: initialDraft.slot,
      requestedKind: initialDraft.requestedKind,
      selection: initialDraft.selection,
      ...(initialDraft.selectionBySlot ? { selectionBySlot: initialDraft.selectionBySlot } : {}),
      blockers: [],
    }
    setEnhancementDraft(selectEnhancementDraftSlotModel(preparingDraft, slot, confirmed))
    setEnhancementLoading(true)

    const hydrated = await hydrateSlot(slot, requestId, false)
    if (hydrated.status !== 'current') {
      if (candidateRequestId.current === requestId) {
        setEnhancementDraft((current) => current && current.slot === slot
          ? { ...current, blockers: ['后端槽位详情不足，无法确认强化'] }
          : current)
        setEnhancementLoading(false)
      }
      return
    }
    const prepared = prepareHydratedEnhancementDraft(hydrated.items, committedItem, confirmed)
    if (!prepared) {
      setEnhancementDraft((current) => current && current.slot === slot
        ? { ...current, blockers: ['未找到已确认物品的完整后端详情'] }
        : current)
      setEnhancementLoading(false)
      return
    }
    const { item: exact, selection } = prepared
    const options = gearEnhancementOptions(exact, { [slot]: selection }, slot)
    const blockers = options.some((option) => option.kind === initialDraft.requestedKind)
      ? []
      : [`当前装备没有可用${initialDraft.requestedKind === 'socket' ? '宝石' : initialDraft.requestedKind === 'enchant' ? '附魔' : '美化'}`]
    if (candidateRequestId.current !== requestId) return
    setEnhancementDraft((current) => {
      if (!current || current.slot !== slot || current.requestedKind !== initialDraft.requestedKind) return current
      return {
        ...selectEnhancementDraftSlotModel(current, slot, selection),
        item: exact,
        blockers,
      }
    })
    setEnhancementLoading(false)
  }

  const openEnhancementGroup = async (item: { id: GearEnhancementKind; label: string }) => {
    const equippedSlots = slotViews.filter((slot) => Boolean(equipped[slot.slot]))
    if (!equippedSlots.length) {
      await Taro.showToast({ title: '请先选择装备', icon: 'none' })
      return
    }
    requestFence.current.replaceDraft()
    setCanonical((current) => current.loading
      ? {
          loading: false,
          ...(current.intent ? { intent: current.intent } : {}),
          ...(current.snapshot ? { snapshot: current.snapshot } : {}),
        }
      : current)
    const target = equippedSlots.find((entry) => entry.slot === selectedSlot) ?? equippedSlots[0]
    if (!target) return
    const confirmed = enhancements[target.slot] ?? emptyEnhancementSelection()
    const initialDraft: GearEnhancementDraft = {
      slot: target.slot,
      requestedKind: item.id,
      selection: packedEnhancementSelection(confirmed),
      selectionBySlot: enhancements,
      blockers: [],
    }
    setCandidateOpen(false)
    setCandidateDraft(null)
    setCandidates([])
    setCandidateLoading(false)
    await selectEnhancementDraftSlot(target.slot, initialDraft)
  }

  const saveTemplate = async () => {
    if (!data || !readiness.selectedCount) return
    setSaving(true)
    try {
      const resolved = await resolveSelection(equipped, enhancements)
      if (resolved.status === 'stale') return
      if (resolved.status !== 'resolved') {
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
        rawString: serializeGearTemplateDraft({ gearBySlot: equipped, enhancementBySlot: enhancements }),
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
      setSavedTemplates(result.payload.templates.filter((template) => template.type === 'gear'))
      await Taro.showToast({ title: result.payload.template ? '装备模板已保存' : '保存失败', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  const importTemplate = async (selection: GearImportSelection) => {
    setImportingTemplate(true)
    candidateRequestId.current += 1
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
    setEnhancementLoading(false)
    const importToken = requestFence.current.beginImport()
    setCanonical((current) => current.loading
      ? {
          loading: false,
          ...(current.intent ? { intent: current.intent } : {}),
          ...(current.snapshot ? { snapshot: current.snapshot } : {}),
        }
      : current)
    try {
      let imported: Readonly<Record<string, GearItemReference>> | null = null
      let importedSnapshot: GearResolvedSnapshot | undefined
      let importedIntent: GearSelectionIntent | undefined
      let importedEnhancements: Readonly<Record<string, GearEnhancementSelection>> = {}
      if (selection.kind === 'community' && data) {
        const templateId = selection.template.id
        if (!templateId) return
        const result = await wowApi.websim.communityTemplateImport({
          classKey: data.selection.classKey,
          specKey: data.selection.specKey,
          templateId,
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
          if (!imported || !importedSnapshot || !importedIntent) {
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
        const draft = selection.kind === 'saved' ? selection.draft : null
        imported = draft?.gearBySlot ?? null
        importedEnhancements = draft?.enhancementBySlot ?? {}
      }
      if (!imported) {
        void Taro.showToast({ title: '没有可导入的真实装备模板', icon: 'none' })
        return
      }
      if (!requestFence.current.isImportCurrent(importToken)) return
      const firstSlot = data?.gear.slots.find((slot) => imported[slot.slot])?.slot
        ?? Object.keys(imported)[0]
        ?? ''
      requestFence.current.replaceDraft()
      candidateRequestId.current += 1
      slotDetailCache.current.clear()
      setEquipped(imported)
      setSelectedSlot(firstSlot)
      setCandidateOpen(false)
      setCandidates([])
      setCandidateDraft(null)
      setEnhancementDraft(null)
      setEnhancementLoading(false)
      setEnhancements(importedEnhancements)
      setStats({ loading: false })
      setDirty(true)
      if (importedSnapshot?.status === 'verified' && importedIntent) {
        setCanonical({ loading: false, intent: importedIntent, snapshot: importedSnapshot })
      } else {
        void resolveSelection(imported, importedEnhancements)
      }
      setImportSheet('closed')
      setWorkbenchNotice(selection.kind === 'community' ? '已原子导入来源模板' : '已导入已保存模板并重新校验')
    } finally {
      setImportingTemplate(false)
    }
  }

  const importSavedTemplate = (templateId: string) => {
    const option = savedTemplateOptions.find((item) => item.template.id === templateId)
    if (option) void importTemplate({ kind: 'saved', ...option })
  }

  const importCommunityTemplate = (templateId: string) => {
    const option = communityTemplateOptions.find((item) => item.template.id === templateId)
    if (option) void importTemplate({ kind: 'community', ...option })
  }

  const reset = () => {
    const hadSelection = readiness.selectedCount > 0
    requestFence.current.replaceDraft()
    candidateRequestId.current += 1
    setCandidateDraft(null)
    setEnhancementDraft(null)
    setEnhancementLoading(false)
    slotDetailCache.current.clear()
    setEquipped({})
    setSelectedSlot('')
    setCandidateOpen(false)
    setCandidates([])
    setCandidateLoading(false)
    setEnhancements({})
    setCanonical({ loading: false })
    setStats({ loading: false })
    setDirty(hadSelection)
    setWorkbenchNotice(hadSelection ? '已清空当前全部装备配置' : '')
  }

  const workbenchEditor = candidateOpen
    ? (
        <GearCandidateEditorSheet
          canApply={Boolean(candidateDraft && candidateDraftCanApply(candidateDraft))}
          candidates={candidateViews}
          draft={candidateDraft}
          loading={candidateLoading || canonical.loading}
          notice={workbenchNotice}
          selectedCandidateId={selectedCandidateId}
          slotLabel={selectedSlotLabel}
          onApply={() => void applyCandidateDraft()}
          onClose={closeCandidateEditor}
          onSelectCandidate={chooseCandidate}
          onSelectVariant={chooseCandidateVariant}
        />
      )
    : enhancementDraft
      ? (
          <GearEnhancementEditorSheet
            activeSlot={enhancementDraft.slot}
            blockers={enhancementDraft.blockers}
            canConfirm={Boolean(enhancementDraft.item && !enhancementDraft.blockers.length)}
            compatibleSlots={enhancementCompatibleSlots}
            draft={enhancementDraft.selection}
            item={enhancementEditorItem}
            loading={enhancementLoading || canonical.loading}
            options={enhancementDraftOptions}
            requestedKind={enhancementDraft.requestedKind}
            socketCount={enhancementSocketCount}
            slotLabel={selectedSlotLabel}
            onClose={closeCandidateEditor}
            onConfirm={() => void confirmEnhancementDraft()}
            onSelectSlot={(slot) => void selectEnhancementDraftSlot(slot)}
            onSetGem={(socketIndex, optionId) => setEnhancementDraft((current) => current
              ? updateEnhancementDraftSelection(current, setGemAtSocket(current.selection, socketIndex, optionId))
              : current)}
            onSetSingle={chooseEnhancement}
          />
        )
      : null

  const actions: readonly GearActionItem[] = route.state.state === 'error' && !data
    ? [
        { id: 'save', label: '重试', tone: 'gold', onClick: () => void route.load() },
        { id: 'import', label: '导入', tone: 'blue', disabled: true, onClick: () => undefined },
        { id: 'reset', label: '重置', tone: 'metal', disabled: true, onClick: () => undefined },
      ]
    : [
        { id: 'save', label: '保存模板', tone: 'gold', disabled: !readiness.selectedCount, loading: saving, onClick: () => void saveTemplate() },
        { id: 'import', label: '导入', tone: 'blue', disabled: !importAvailable, onClick: () => setImportSheet('saved') },
        { id: 'reset', label: '重置', tone: 'metal', disabled: !data || !readiness.selectedCount, onClick: reset },
      ]

  if (queryMode !== 'gear') {
    return <AppShell><PageFrame title="正在跳转天赋模拟" variant="gear-detail"><StatusVisual state="loading" /></PageFrame></AppShell>
  }

  return (
    <AppShell
      bodyScrollable={false}
      surfaceMaterialFamily="build-workspace"
      surfaceSlotId="asset_slot.gear-detail-surface"
    >
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={route.state.state} targetRegionCount={8} width="full">
        <PageFrame
          backRegion="header_nav.back-control"
          region="header_nav"
          title="装备详情"
          variant="gear-detail"
          onBack={() => goBack('/pages/builds/builds')}
        >
          <View className={styles['surface'] ?? ''} data-region="page_frame">
            <RouteRegion className={styles['professionRegion'] ?? ''} data-region="profession_selector">
              <GearProfessionSelector
                items={classItems}
                loading={initialLoading}
                selectedIndex={selectedClassIndex}
                value={selectedClassLabel}
                onSelect={selectProfession}
              />
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
            <RouteRegion className={styles['loadoutSummaryRegion'] ?? ''} data-region="loadout_summary">
              <GearLoadoutSummary {...readiness} />
            </RouteRegion>
            <RouteRegion className={styles['enhancementRegion'] ?? ''} data-region="enhancement_summary">
              <GearEnhancementBar items={enhancementGroups} onSelect={(item) => void openEnhancementGroup(item)} />
            </RouteRegion>
            <RouteRegion className={styles['workbenchRegion'] ?? ''} data-region="gear_workbench">
              <GearSlotWorkbench
                candidateOpen={candidateOpen}
                candidateLoading={candidateLoading}
                candidates={candidateViews}
                editor={workbenchEditor}
                enhancements={enhancementOptions}
                notice={workbenchNotice}
                committedSlotVariantKey={committedSlotVariantKey}
                resolvedSlotItemId={resolvedSlotItemId}
                resolvedSlotVariantKey={resolvedSlotVariantKey}
                resolveState={gearResolveState}
                selectedSlot={selectedSlot}
                selectedSlotLabel={selectedSlotLabel}
                slots={slotViews}
                onCandidate={(item) => chooseCandidate(item.id)}
                onClose={closeCandidateEditor}
                onEnhancement={(item) => {
                  if (item.kind !== 'socket') chooseEnhancement(item.kind, item.id)
                }}
                onSlot={(item) => void chooseSlot(item)}
              />
            </RouteRegion>
            <RouteRegion className={styles['actionsRegion'] ?? ''} data-region="gear_actions"><GearActionRow items={actions} /></RouteRegion>
          </View>
          <GearTemplateImportSheet
            visible={importSheet !== 'closed'}
            activeTab={importSheet === 'community' ? 'community' : 'saved'}
            savedItems={savedImportItems}
            communityItems={communityImportItems}
            importing={importingTemplate}
            onTabChange={setImportSheet}
            onClose={() => {
              if (!importingTemplate) setImportSheet('closed')
            }}
            onImportSaved={importSavedTemplate}
            onImportCommunity={importCommunityTemplate}
          />
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
