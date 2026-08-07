import Taro, { useRouter } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import {
  taroStorage,
  wowApi,
  type ExactSimcConfirmation,
  type ExactSimcRequest,
} from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import { dataSelectorClass } from '@wow-mini/design-system/components/selector-markers'
import {
  SimcBlockerPanel,
  SimcCombatConfiguration,
  SimcFooterNotice,
  SimcIdentitySelectors,
  SimcPreSubmitSummary,
  SimcRecordAction,
  SimcSubmissionActionBar,
  SimcTemplateSlot,
  type SimcSpecializationItem,
} from '@wow-mini/design-system/components/SimcSubmitComponents'
import {
  storageKey,
  type BuildTemplate,
  type BuildsHomePayload,
  type ReadinessState,
  type SimcBuildContext,
  type SimcOptionsPayload,
  type SimulatorTaskRecord,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  flattenSpecs,
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
  buildCanonicalSimcContext,
  canonicalSimcBuildIntent,
  createSimcSubmissionSession,
  deriveSimcOptionsView,
  simcCanPrepare,
  simcBlockerRows,
  simcConfirmationLabel,
  simcGearSources,
  simcSummaryRows,
  simcTemplateSlot,
  simcRouteFromFallback,
  type SimcBuffRuleView,
  type SimcOptionsView,
  type SimcTemplateSlotView,
} from './simc-submit-model'
import styles from './simc-submit.module.scss'

interface SimcPagePayload {
  home: BuildsHomePayload
  selection: SpecSelection
  options: SimcOptionsPayload
  buildContext?: SimcBuildContext | undefined
  talentTemplates: readonly BuildTemplate[]
  gearTemplates: readonly BuildTemplate[]
  tasks: readonly SimulatorTaskRecord[]
}

interface ConfirmationState {
  state: ReadinessState
  error?: string
  request?: ExactSimcRequest
  confirmation?: ExactSimcConfirmation
}

const blockedOptionsView: SimcOptionsView = {
  state: 'blocked',
  specializationSupported: false,
  specializationBlockerCode: 'SIMC_SPECIALIZATION_POLICY_UNAVAILABLE',
  specializationBlockerDetail: '后端没有返回可验证的 SimC 专精支持策略。',
  races: [],
  scenarios: [],
  selectedRaceKey: '',
  selectedRaceIndex: 0,
  selectedScenarioKey: '',
  selectedScenarioIndex: 0,
  durationSeconds: undefined,
  targets: undefined,
  preparationRows: [],
}

function activeTask(task: SimulatorTaskRecord): boolean {
  const status = task.status.toLowerCase()
  return status === 'queued' || status === 'running' || status === 'processing'
}

function compatibleTemplates(
  templates: readonly BuildTemplate[],
  selection: SpecSelection | undefined,
): readonly BuildTemplate[] {
  if (!selection) return []
  return templates.filter((template) => (
    template.classKey === selection.classKey
    && template.specKey === selection.specKey
  ))
}

function envelopeMessage(
  problems: readonly { code?: string; detail?: string; title?: string; kind?: string }[],
  fallback: string,
): string {
  return problems
    .map((problem) => problem.detail || problem.title || problem.code || problem.kind || '')
    .filter(Boolean)
    .join(' / ') || fallback
}

function preparationState(evidenceState: string): SimcBuffRuleView['state'] {
  if (evidenceState === 'verified') return 'ready'
  if (evidenceState === 'blocked') return 'blocked'
  return 'partial'
}

export default function SimcSubmitPage() {
  const router = useRouter()
  const initialSpec = safeDecode(router.params['spec'])
  const [selectedSpecId, setSelectedSpecId] = useState(initialSpec)
  const [talentTemplateId, setTalentTemplateId] = useState('')
  const [gearSourceId, setGearSourceId] = useState('')
  const [selectedRaceKey, setSelectedRaceKey] = useState('')
  const [selectedScenarioKey, setSelectedScenarioKey] = useState(safeDecode(router.params['scenario']))
  const [confirmation, setConfirmation] = useState<ConfirmationState>({ state: 'unknown' })
  const [submitting, setSubmitting] = useState(false)
  const submittingRef = useRef(false)
  const [submittedTaskId, setSubmittedTaskId] = useState('')
  const selectionChanged = useRef(false)
  const submissionSession = useRef(createSimcSubmissionSession())

  useEffect(() => {
    submissionSession.current.mount()
    return () => submissionSession.current.unmount()
  }, [])

  const route = useAsyncRoute<SimcPagePayload>(async () => {
    const storedBuildContext = taroStorage.get<unknown>(storageKey('simc.buildContext'))
    const [homeResult, optionsResult, talentsResult, gearResult, tasksResult] = await Promise.all([
      wowApi.builds.home(),
      wowApi.simulator.options(),
      wowApi.templates.fetch('talent'),
      wowApi.templates.fetch('gear'),
      wowApi.simulator.tasks(),
    ])
    const keyMatch = flattenSpecs(homeResult.payload.classOptions).find((entry) => (
      entry.spec.websimClassKey === safeDecode(router.params['classKey'])
      && entry.spec.websimSpecKey === safeDecode(router.params['specKey'])
    ))
    const contextMatch = flattenSpecs(homeResult.payload.classOptions).find((entry) => (
      canonicalSimcBuildIntent(
        storedBuildContext,
        entry.spec.websimClassKey ?? '',
        entry.spec.websimSpecKey ?? '',
      ) !== null
    ))
    const selection = findSpecSelection(
      homeResult.payload,
      selectedSpecId || keyMatch?.spec.id || contextMatch?.spec.id || defaultSpecId,
    )
    if (!selection) throw new Error('没有可用的职业专精映射')
    const buildContext = canonicalSimcBuildIntent(
      storedBuildContext,
      selection.classKey,
      selection.specKey,
    ) ? storedBuildContext as SimcBuildContext : undefined
    return {
      payload: {
        home: homeResult.payload,
        selection,
        options: optionsResult.payload,
        ...(buildContext ? { buildContext } : {}),
        talentTemplates: talentsResult.payload.templates,
        gearTemplates: gearResult.payload.templates,
        tasks: tasksResult.fromFallback ? [] : tasksResult.payload.tasks,
      },
      fromFallback: simcRouteFromFallback({
        homeFromFallback: homeResult.fromFallback,
        optionsFromFallback: optionsResult.fromFallback,
        talentsFromFallback: talentsResult.fromFallback,
        tasksFromFallback: tasksResult.fromFallback,
      }),
      error: [homeResult.error, optionsResult.error, tasksResult.error]
        .filter(Boolean)
        .join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    submissionSession.current.invalidate()
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
    void route.load()
  }, [selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    const talents = compatibleTemplates(route.data.talentTemplates, route.data.selection)
    const gearSources = simcGearSources({
      buildContext: route.data.buildContext,
      templates: route.data.gearTemplates,
      classKey: route.data.selection.classKey,
      specKey: route.data.selection.specKey,
      specializationLabel: route.data.selection.label,
    })
    setTalentTemplateId((current) => talents.some((item) => item.id === current) ? current : talents[0]?.id || '')
    setGearSourceId((current) => gearSources.some((item) => item.id === current) ? current : gearSources[0]?.id || '')
  }, [route.data])

  const data = route.data
  const resolvedClassKey = data?.selection.classKey
  const resolvedSpecId = data?.selection.specId
  useEffect(() => {
    if (!data?.selection || !resolvedClassKey || !resolvedSpecId) return
    rememberBuildsHomeSpec(data.selection)
  }, [resolvedClassKey, resolvedSpecId])

  const talentTemplates = compatibleTemplates(data?.talentTemplates ?? [], data?.selection)
  const talentTemplate = talentTemplates.find((template) => template.id === talentTemplateId)
  const gearSources = data ? simcGearSources({
    buildContext: data.buildContext,
    templates: data.gearTemplates,
    classKey: data.selection.classKey,
    specKey: data.selection.specKey,
    specializationLabel: data.selection.label,
  }) : []
  const selectedGearSource = gearSources.find((source) => source.id === gearSourceId) ?? gearSources[0]
  const activeBuildContext = selectedGearSource?.buildContext
  const activeTasks = data?.tasks.filter(activeTask) ?? []
  const optionsView = data
    ? deriveSimcOptionsView(
      data.options,
      data.selection.classKey,
      data.selection.specKey,
      selectedRaceKey || activeBuildContext?.raceKey || '',
      selectedScenarioKey,
    )
    : blockedOptionsView
  const canonicalContext = data
    ? buildCanonicalSimcContext({
      buildContext: activeBuildContext,
      gearSource: selectedGearSource,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      raceKey: optionsView.selectedRaceKey,
      scenarioKey: optionsView.selectedScenarioKey,
      talentTemplate,
    })
    : null
  const gearContextAvailable = Boolean(data && canonicalSimcBuildIntent(
    activeBuildContext,
    data.selection.classKey,
    data.selection.specKey,
  ))
  const canPrepare = simcCanPrepare({
    routeState: route.state.state,
    optionsState: optionsView.state,
    canonicalContextAvailable: Boolean(canonicalContext),
    activeTaskCount: activeTasks.length,
    submitting,
  })

  const invalidateConfirmation = () => {
    submissionSession.current.invalidate()
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
  }

  const buildRequest = (): ExactSimcRequest | null => {
    if (!canonicalContext) return null
    return {
      selectionIntent: canonicalContext.selectionIntent,
      sourceRef: canonicalContext.sourceRef,
      profileRef: canonicalContext.profileRef,
      executionIntent: canonicalContext.executionIntent,
    }
  }

  const confirm = async () => {
    if (submittingRef.current) return
    const request = buildRequest()
    if (!request || !canPrepare || !canonicalContext) return
    const token = submissionSession.current.begin()
    if (!submissionSession.current.isCurrent(token)) return
    setConfirmation({ state: 'loading' })
    try {
      const result = await wowApi.simulator.exactSimcConfirm(request)
      if (!submissionSession.current.isCurrent(token)) return
      if (result.fromFallback) {
        setConfirmation({ state: 'blocked', error: result.error || '组合校验请求失败，请重试。' })
        return
      }
      if (result.payload.status !== 'ready') {
        setConfirmation({
          state: 'blocked',
          error: envelopeMessage(result.payload.problems, '属性快照未通过后端校验'),
        })
        return
      }
      setConfirmation({
        state: 'ready',
        request,
        confirmation: result.payload.data,
      })
    } catch (error) {
      if (!submissionSession.current.isCurrent(token)) return
      setConfirmation({
        state: 'error',
        error: error instanceof Error ? error.message : '组合校验请求失败，请重试。',
      })
    }
  }

  const submit = async () => {
    if (confirmation.state !== 'ready'
      || !confirmation.request
      || !confirmation.confirmation
      || submittingRef.current) return
    const token = submissionSession.current.begin()
    if (!submissionSession.current.isCurrent(token)) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      const gate = await wowApi.simulator.tasks()
      if (!submissionSession.current.isCurrent(token)) return
      if (gate.fromFallback || gate.payload.tasks.some(activeTask)) {
        setConfirmation({ state: 'blocked', error: gate.error || '已有活动任务，请等待完成后再提交。' })
        return
      }
      if (!submissionSession.current.isCurrent(token)) return
      const result = await wowApi.simulator.exactSimcSubmit(
        confirmation.request,
        confirmation.confirmation,
      )
      if (!submissionSession.current.isCurrent(token)) return
      if (result.fromFallback) {
        setConfirmation({ state: 'error', error: result.error || '提交失败，请重试。' })
        return
      }
      if (result.payload.status !== 'queued') {
        setConfirmation({
          state: 'blocked',
          error: envelopeMessage(result.payload.problems, '后端没有返回 taskId'),
        })
        return
      }
      const readResult = await wowApi.simulator.exactSimcRead(result.payload.data.jobId)
      if (!submissionSession.current.isCurrent(token)) return
      if (readResult.fromFallback) {
        setConfirmation({ state: 'blocked', error: readResult.error || '后端没有返回 taskId' })
        return
      }
      if (readResult.payload.status === 'blocked'
        || readResult.payload.status === 'unsupported'
        || readResult.payload.status === 'failed') {
        setConfirmation({
          state: 'blocked',
          error: envelopeMessage(readResult.payload.problems, '后端没有返回 taskId'),
        })
        return
      }
      if (!submissionSession.current.isCurrent(token)) return
      setSubmittedTaskId(String(result.payload.data.jobId))
      await Taro.showToast({ title: '任务已提交', icon: 'none' })
      if (!submissionSession.current.isCurrent(token)) return
    } catch (error) {
      if (!submissionSession.current.isCurrent(token)) return
      setConfirmation({
        state: 'error',
        error: error instanceof Error ? error.message : '提交失败，请重试。',
      })
    } finally {
      submittingRef.current = false
      if (submissionSession.current.isCurrent(token)) {
        setSubmitting(false)
      }
    }
  }

  const allSpecs = data ? flattenSpecs(data.home.classOptions) : []
  const specializationItems: readonly SimcSpecializationItem[] = allSpecs.flatMap(({ classItem, spec }) => {
    const id = spec.id || spec.specId || ''
    if (!id) return []
    return [{
      id,
      label: spec.specName || spec.title || spec.name,
      classLabel: classItem.name,
      ...((spec.specIconUrl || spec.iconUrl) ? { iconUrl: spec.specIconUrl || spec.iconUrl } : {}),
    }]
  })
  const talentSlot = simcTemplateSlot('talent', talentTemplates, talentTemplateId)
  const gearContextLabel = gearContextAvailable
    ? `${selectedGearSource?.label || data?.selection.label || '当前专精'} · canonical intent 已带入`
    : ''
  const gearSlot: SimcTemplateSlotView = {
    type: 'gear',
    title: '装备来源',
    sourceLabel: selectedGearSource?.kind === 'template' ? '来自装备模板' : '来自装备详情',
    valueLabel: selectedGearSource?.label || '未带入装备配置',
    helperLabel: selectedGearSource?.helperLabel || '请从装备详情带入或保存有效模板',
    state: selectedGearSource?.state ?? 'blocked',
    options: gearSources.map((source) => source.label),
    selectedIndex: Math.max(0, gearSources.findIndex((source) => source.id === selectedGearSource?.id)),
  }
  const preparationRules: readonly SimcBuffRuleView[] = optionsView.preparationRows.length
    ? optionsView.preparationRows.map((row) => ({
      id: row.key,
      label: row.label,
      value: `${row.defaultState} · ${row.overrideSupported ? '支持覆盖' : '只读'}`,
      state: preparationState(row.evidenceState),
      overrideSupported: row.overrideSupported,
    }))
    : [{
      id: 'options-unavailable',
      label: '准备规则',
      value: optionsView.state === 'empty' ? '后端未返回可用规则' : '等待后端选项',
      state: 'blocked',
    }]
  const selectedScenario = data?.options.scenarios.find((scenario) => (
    scenario.key === optionsView.selectedScenarioKey
  ))
  const preparationSummaryState = preparationRules.some((rule) => rule.state === 'blocked')
    ? 'blocked' as const
    : preparationRules.some((rule) => rule.state === 'partial')
      ? 'partial' as const
      : 'ready' as const
  const preparationLabel = optionsView.preparationRows.length
    ? `${optionsView.preparationRows.length} 项后端规则 · ${
      optionsView.preparationRows.some((row) => row.overrideSupported) ? '含可覆盖项' : '只读'
    }`
    : '后端未返回准备规则'
  const modelInput = {
    specializationLabel: data?.selection.label ?? '',
    specializationSupported: optionsView.specializationSupported,
    ...(optionsView.specializationBlockerDetail
      ? { specializationBlockerDetail: optionsView.specializationBlockerDetail }
      : {}),
    raceLabel: optionsView.selectedRaceKey,
    scenarioLabel: selectedScenario?.label ?? '',
    ...(optionsView.targets !== undefined ? { scenarioTargets: optionsView.targets } : {}),
    ...(optionsView.durationSeconds !== undefined ? { durationSeconds: optionsView.durationSeconds } : {}),
    ...(talentTemplate ? { talentTemplate } : {}),
    gearContextAvailable,
    ...(gearContextLabel ? { gearContextLabel } : {}),
    preparationLabel,
    preparationState: preparationSummaryState,
    activeTaskCount: activeTasks.length,
    confirmationState: confirmation.state,
    ...(confirmation.error ? { confirmationError: confirmation.error } : {}),
  }
  const confirmationView = simcConfirmationLabel(confirmation.state, submitting, submittedTaskId)
  const loading = route.state.state === 'loading' && !data
  const simcSpecializationId = data
    ? `${data.selection.classKey}:${data.selection.specKey}`
    : ''

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.simc-page-frame"
    >
      <RouteStage
        className={styles['pageFrame'] ?? ''}
        routeState={route.state.state}
        targetRegionCount={10}
        width="inset"
      >
        <PageFrame
          backRegion="simc-submit-back"
          region="header_nav"
          rightAction={<SimcRecordAction onClick={() => navigateTo('/pages/simulator/tasks', { from: 'simc' })} />}
          title="模拟 SimC"
          variant="simc-submit"
          onBack={() => goBack('/pages/builds/workbench')}
        >
          <RouteRegion className={styles['identityRegion'] ?? ''} data-region="character_identity">
            <SimcIdentitySelectors
              disabled={submitting}
              loading={loading}
              races={optionsView.races}
              selectedRaceIndex={optionsView.selectedRaceIndex}
              selectedSpecializationId={data?.selection.specId ?? selectedSpecId}
              specializations={specializationItems}
              onRaceSelect={(index) => {
                if (submittingRef.current) return
                const next = optionsView.races[index]
                if (!next) return
                invalidateConfirmation()
                setSelectedRaceKey(next.id)
              }}
              onSpecializationSelect={(id) => {
                if (submittingRef.current) return
                invalidateConfirmation()
                setSelectedSpecId(id)
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['talentRegion'] ?? ''} data-region="talent_template">
            <SimcTemplateSlot
              {...talentSlot}
              disabled={submitting}
              loading={loading}
              onSelect={(index) => {
                if (submittingRef.current) return
                const next = talentTemplates[index]
                if (!next) return
                invalidateConfirmation()
                setTalentTemplateId(next.id)
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['gearRegion'] ?? ''} data-region="gear_source">
            <SimcTemplateSlot
              {...gearSlot}
              disabled={submitting}
              loading={loading}
              onSelect={(index) => {
                if (submittingRef.current) return
                const next = gearSources[index]
                if (!next) return
                invalidateConfirmation()
                setGearSourceId(next.id)
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['combatRegion'] ?? ''} data-region="combat_parameters">
            <SimcCombatConfiguration
              buffRules={preparationRules}
              disabled={submitting}
              durationSeconds={optionsView.durationSeconds}
              scenarios={optionsView.scenarios}
              selectedScenarioIndex={optionsView.selectedScenarioIndex}
              onScenarioSelect={(index) => {
                if (submittingRef.current) return
                const next = optionsView.scenarios[index]
                if (!next) return
                invalidateConfirmation()
                setSelectedScenarioKey(next.id)
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['summaryRegion'] ?? ''} data-region="submission_summary">
            <SimcPreSubmitSummary items={simcSummaryRows(modelInput)} />
          </RouteRegion>
          <RouteRegion className={styles['blockerRegion'] ?? ''} data-region="submission_blockers">
            <SimcBlockerPanel items={simcBlockerRows(modelInput)} />
          </RouteRegion>
          <RouteRegion
            className={[
              styles['actionRegion'] ?? '',
              dataSelectorClass('simc-specialization-id', simcSpecializationId),
              dataSelectorClass('simc-specialization-supported', optionsView.specializationSupported),
              dataSelectorClass('simc-specialization-blocker-code', optionsView.specializationBlockerCode || 'none'),
              dataSelectorClass('simc-options-state', optionsView.state),
            ].filter(Boolean).join(' ')}
            data-region="submission_action"
            data-simc-options-state={optionsView.state}
            data-simc-specialization-blocker-code={optionsView.specializationBlockerCode || 'none'}
            data-simc-specialization-id={simcSpecializationId}
            data-simc-specialization-supported={optionsView.specializationSupported}
          >
            <SimcSubmissionActionBar
              canConfirm={canPrepare}
              canSubmit={confirmation.state === 'ready'}
              confirming={confirmation.state === 'loading'}
              detail={confirmation.error || confirmationView.detail}
              state={confirmationView.state}
              submittedTaskId={submittedTaskId}
              submitting={submitting}
              title={confirmationView.title}
              onConfirm={() => void confirm()}
              onSubmit={() => void submit()}
              onViewTask={() => navigateTo('/pages/simulator/task-detail', { id: submittedTaskId })}
            />
          </RouteRegion>
          <RouteRegion className={styles['footerRegion'] ?? ''} data-region="submission_footer">
            <SimcFooterNotice
              actionLabel={data ? '任务规则' : '重新读取'}
              onAction={data ? () => navigateTo('/pages/simulator/tasks', { from: 'simc-rules' }) : route.load}
            />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
