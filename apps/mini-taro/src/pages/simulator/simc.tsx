import Taro, { useRouter } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import { taroStorage, wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
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
  type GearProblem,
  type GearStatsPayload,
  type ReadinessState,
  type SimcBuildContext,
  type SimcOptionsPayload,
  type SimulatorAnalysisResponse,
  type SimulatorTaskRecord,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  flattenSpecs,
  type SpecSelection,
} from '../_shared/build-context'
import {
  goBack,
  navigateTo,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  buildCanonicalSimcContext,
  deriveSimcOptionsView,
  simcBlockerRows,
  simcConfirmationLabel,
  simcSummaryRows,
  simcTemplateSlot,
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
  tasks: readonly SimulatorTaskRecord[]
}

interface ConfirmationState {
  state: ReadinessState
  error?: string
  request?: Readonly<Record<string, unknown>>
  response?: SimulatorAnalysisResponse
  stats?: GearStatsPayload
}

const blockedOptionsView: SimcOptionsView = {
  state: 'blocked',
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function activeTask(task: SimulatorTaskRecord): boolean {
  const status = task.status.toLowerCase()
  return status === 'queued' || status === 'running' || status === 'processing'
}

function explicitValidationPassed(response: SimulatorAnalysisResponse): boolean {
  if (!isRecord(response.agent)) return false
  const validation = response.agent['validation']
  return isRecord(validation) && validation['passed'] === true
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

function envelopeMessage(problems: readonly GearProblem[], fallback: string): string {
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
  const [selectedRaceKey, setSelectedRaceKey] = useState('')
  const [selectedScenarioKey, setSelectedScenarioKey] = useState(safeDecode(router.params['scenario']))
  const [confirmation, setConfirmation] = useState<ConfirmationState>({ state: 'unknown' })
  const [submitting, setSubmitting] = useState(false)
  const [submittedTaskId, setSubmittedTaskId] = useState('')
  const selectionChanged = useRef(false)
  const confirmationRequestId = useRef(0)

  const route = useAsyncRoute<SimcPagePayload>(async () => {
    const buildContext = taroStorage.get<SimcBuildContext>(storageKey('simc.buildContext'))
    const [homeResult, optionsResult, talentsResult, tasksResult] = await Promise.all([
      wowApi.builds.home(),
      wowApi.simulator.options(),
      wowApi.templates.fetch('talent'),
      wowApi.simulator.tasks(),
    ])
    const keyMatch = flattenSpecs(homeResult.payload.classOptions).find((entry) => (
      entry.spec.websimClassKey === safeDecode(router.params['classKey'])
      && entry.spec.websimSpecKey === safeDecode(router.params['specKey'])
    ))
    const selection = findSpecSelection(
      homeResult.payload,
      selectedSpecId || buildContext?.specId || keyMatch?.spec.id || defaultSpecId,
    )
    if (!selection) throw new Error('没有可用的职业专精映射')
    return {
      payload: {
        home: homeResult.payload,
        selection,
        options: optionsResult.payload,
        ...(buildContext ? { buildContext } : {}),
        talentTemplates: talentsResult.payload.templates,
        tasks: tasksResult.fromFallback ? [] : tasksResult.payload.tasks,
      },
      fromFallback: homeResult.fromFallback
        || optionsResult.fromFallback
        || talentsResult.fromFallback
        || tasksResult.fromFallback,
      error: [homeResult.error, optionsResult.error, talentsResult.error, tasksResult.error]
        .filter(Boolean)
        .join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    confirmationRequestId.current += 1
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
    void route.load()
  }, [selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    const talents = compatibleTemplates(route.data.talentTemplates, route.data.selection)
    setTalentTemplateId((current) => talents.some((item) => item.id === current) ? current : talents[0]?.id || '')
  }, [route.data])

  const data = route.data
  const talentTemplates = compatibleTemplates(data?.talentTemplates ?? [], data?.selection)
  const talentTemplate = talentTemplates.find((template) => template.id === talentTemplateId)
  const activeTasks = data?.tasks.filter(activeTask) ?? []
  const optionsView = data
    ? deriveSimcOptionsView(
      data.options,
      data.selection.classKey,
      data.selection.specKey,
      selectedRaceKey || data.buildContext?.raceKey || '',
      selectedScenarioKey,
    )
    : blockedOptionsView
  const canonicalContext = data
    ? buildCanonicalSimcContext({
      buildContext: data.buildContext,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      raceKey: optionsView.selectedRaceKey,
      scenarioKey: optionsView.selectedScenarioKey,
      talentTemplate,
    })
    : null
  const gearContextAvailable = Boolean(
    data?.buildContext
    && data.buildContext.classKey === data.selection.classKey
    && data.buildContext.specKey === data.selection.specKey
    && data.buildContext.selectionIntent,
  )
  const canPrepare = route.state.state === 'ready'
    && optionsView.state === 'ready'
    && Boolean(canonicalContext)
    && activeTasks.length === 0

  const invalidateConfirmation = () => {
    confirmationRequestId.current += 1
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
  }

  const buildRequest = (): Readonly<Record<string, unknown>> | null => {
    if (!canonicalContext) return null
    return {
      mode: 'simcraft_template',
      confirmOnly: true,
      saveTask: false,
      selectionIntent: canonicalContext.selectionIntent,
      profileContext: canonicalContext.profileContext,
    }
  }

  const confirm = async () => {
    const request = buildRequest()
    if (!request || !canPrepare || !canonicalContext) return
    const requestId = confirmationRequestId.current + 1
    confirmationRequestId.current = requestId
    setConfirmation({ state: 'loading' })
    try {
      const startedAt = Date.now()
      for (let attempt = 0; attempt < 15 && Date.now() - startedAt < 45000; attempt += 1) {
        const statsResult = await wowApi.websim.gearStatSnapshot({
          selectionIntent: canonicalContext.selectionIntent,
          profileContext: canonicalContext.profileContext,
          timeoutMs: Math.max(1, 45000 - (Date.now() - startedAt)),
        })
        if (confirmationRequestId.current !== requestId) return
        if (statsResult.fromFallback) {
          setConfirmation({ state: 'blocked', error: statsResult.error || '属性快照服务不可用' })
          return
        }
        const snapshot = statsResult.payload.data.statSnapshot
        if (statsResult.httpStatus === 200
          && statsResult.payload.status === 'resolved'
          && snapshot?.statStatus === 'verified') {
          const confirmedRequest = { ...request, statSnapshot: snapshot }
          const result = await wowApi.simulator.analyze(confirmedRequest)
          if (confirmationRequestId.current !== requestId) return
          if (result.fromFallback || !explicitValidationPassed(result.payload)) {
            setConfirmation({
              state: 'blocked',
              error: result.error || '后端没有明确返回 validation.passed=true',
              response: result.payload,
              stats: snapshot,
            })
            return
          }
          setConfirmation({
            state: 'ready',
            request: confirmedRequest,
            response: result.payload,
            stats: snapshot,
          })
          return
        }
        if (statsResult.httpStatus !== 202 || statsResult.payload.status !== 'pending') {
          setConfirmation({
            state: 'blocked',
            error: envelopeMessage(statsResult.payload.problems, '属性快照未通过后端校验'),
          })
          return
        }
        const delay = Math.min(5000, Math.max(250, Number(statsResult.payload.data.retryAfterMs) || 1500))
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
      if (confirmationRequestId.current === requestId) {
        setConfirmation({ state: 'blocked', error: '属性快照等待超时' })
      }
    } catch (error) {
      if (confirmationRequestId.current !== requestId) return
      setConfirmation({
        state: 'error',
        error: error instanceof Error ? error.message : '组合校验请求失败，请重试。',
      })
    }
  }

  const submit = async () => {
    if (confirmation.state !== 'ready' || !confirmation.request || submitting) return
    setSubmitting(true)
    try {
      const gate = await wowApi.simulator.tasks()
      if (gate.fromFallback || gate.payload.tasks.some(activeTask)) {
        setConfirmation({ state: 'blocked', error: gate.error || '已有活动任务，请等待完成后再提交。' })
        return
      }
      const result = await wowApi.simulator.analyze({
        ...confirmation.request,
        confirmOnly: false,
        saveTask: true,
      }, { auth: true, allowInsecureGuestRequest: true })
      if (result.fromFallback || !result.payload.taskId) {
        setConfirmation({ state: 'error', error: result.error || '后端没有返回 taskId' })
        return
      }
      setSubmittedTaskId(result.payload.taskId)
      await Taro.showToast({ title: '任务已提交', icon: 'none' })
    } catch (error) {
      setConfirmation({
        state: 'error',
        error: error instanceof Error ? error.message : '提交失败，请重试。',
      })
    } finally {
      setSubmitting(false)
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
    ? `${data?.buildContext?.specName || data?.selection.label || '当前专精'} · canonical intent 已带入`
    : ''
  const gearSlot: SimcTemplateSlotView = {
    type: 'gear',
    title: '装备来源',
    sourceLabel: '来自装备详情',
    valueLabel: gearContextLabel || '未带入装备配置',
    helperLabel: gearContextAvailable ? '本机意图待本次后端快照校验' : '请从装备详情带入',
    state: gearContextAvailable ? 'partial' : 'blocked',
    options: [],
    selectedIndex: 0,
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
              loading={loading}
              races={optionsView.races}
              selectedRaceIndex={optionsView.selectedRaceIndex}
              selectedSpecializationId={data?.selection.specId ?? selectedSpecId}
              specializations={specializationItems}
              onRaceSelect={(index) => {
                const next = optionsView.races[index]
                if (!next) return
                setSelectedRaceKey(next.id)
                invalidateConfirmation()
              }}
              onSpecializationSelect={setSelectedSpecId}
            />
          </RouteRegion>
          <RouteRegion className={styles['talentRegion'] ?? ''} data-region="talent_template">
            <SimcTemplateSlot
              {...talentSlot}
              loading={loading}
              onSelect={(index) => {
                const next = talentTemplates[index]
                if (!next) return
                setTalentTemplateId(next.id)
                invalidateConfirmation()
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['gearRegion'] ?? ''} data-region="gear_source">
            <SimcTemplateSlot {...gearSlot} loading={loading} onSelect={() => {}} />
          </RouteRegion>
          <RouteRegion className={styles['combatRegion'] ?? ''} data-region="combat_parameters">
            <SimcCombatConfiguration
              buffRules={preparationRules}
              durations={optionsView.durationSeconds === undefined ? [] : [optionsView.durationSeconds]}
              scenarios={optionsView.scenarios}
              selectedDurationIndex={0}
              selectedScenarioIndex={optionsView.selectedScenarioIndex}
              onDurationSelect={() => {}}
              onScenarioSelect={(index) => {
                const next = optionsView.scenarios[index]
                if (!next) return
                setSelectedScenarioKey(next.id)
                invalidateConfirmation()
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['summaryRegion'] ?? ''} data-region="submission_summary">
            <SimcPreSubmitSummary items={simcSummaryRows(modelInput)} />
          </RouteRegion>
          <RouteRegion className={styles['blockerRegion'] ?? ''} data-region="submission_blockers">
            <SimcBlockerPanel items={simcBlockerRows(modelInput)} />
          </RouteRegion>
          <RouteRegion className={styles['actionRegion'] ?? ''} data-region="submission_action">
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
