import Taro, { useRouter } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
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
import type {
  BuildTemplate,
  BuildsHomePayload,
  GearStatsPayload,
  ReadinessState,
  SimulatorAnalysisResponse,
  SimulatorTaskRecord,
} from '@wow-mini/domain'

import {
  defaultSpecId,
  findSpecSelection,
  flattenSpecs,
  scenarioOptions,
  type SpecSelection,
} from '../_shared/build-context'
import {
  goBack,
  navigateTo,
  safeDecode,
  useAsyncRoute,
} from '../_shared/route-runtime'
import {
  simcBlockerRows,
  simcBuffRules,
  simcConfirmationLabel,
  simcSummaryRows,
  simcTemplateSlot,
} from './simc-submit-model'
import styles from './simc-submit.module.scss'

interface SimcPagePayload {
  home: BuildsHomePayload
  selection: SpecSelection
  talentTemplates: readonly BuildTemplate[]
  gearTemplates: readonly BuildTemplate[]
  tasks: readonly SimulatorTaskRecord[]
}

interface ConfirmationState {
  state: ReadinessState
  error?: string
  request?: Readonly<Record<string, unknown>>
  response?: SimulatorAnalysisResponse
  stats?: GearStatsPayload
}

const races = [
  { id: 'human', label: '人类' },
  { id: 'orc', label: '兽人' },
  { id: 'night_elf', label: '暗夜精灵' },
  { id: 'dwarf', label: '矮人' },
  { id: 'blood_elf', label: '血精灵' },
] as const

const durations = [180, 300, 360] as const

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function activeTask(task: SimulatorTaskRecord): boolean {
  const status = task.status.toLowerCase()
  return status === 'queued' || status === 'running' || status === 'processing'
}

function parsedGear(template: BuildTemplate): Readonly<Record<string, unknown>> | null {
  try {
    const parsed: unknown = JSON.parse(template.rawString)
    return isRecord(parsed) ? parsed : null
  } catch {
    return null
  }
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

export default function SimcSubmitPage() {
  const router = useRouter()
  const initialSpec = safeDecode(router.params['spec'])
  const [selectedSpecId, setSelectedSpecId] = useState(initialSpec)
  const [talentTemplateId, setTalentTemplateId] = useState('')
  const [gearTemplateId, setGearTemplateId] = useState('')
  const [raceIndex, setRaceIndex] = useState(0)
  const [scenarioIndex, setScenarioIndex] = useState(Math.max(0, scenarioOptions.findIndex((item) => item.key === safeDecode(router.params['scenario']))))
  const [durationIndex, setDurationIndex] = useState(1)
  const [confirmation, setConfirmation] = useState<ConfirmationState>({ state: 'unknown' })
  const [submitting, setSubmitting] = useState(false)
  const [submittedTaskId, setSubmittedTaskId] = useState('')
  const selectionChanged = useRef(false)

  const route = useAsyncRoute<SimcPagePayload>(async () => {
    const [homeResult, talentsResult, gearResult, tasksResult] = await Promise.all([
      wowApi.builds.home(),
      wowApi.templates.fetch('talent'),
      wowApi.templates.fetch('gear'),
      wowApi.simulator.tasks(),
    ])
    const keyMatch = flattenSpecs(homeResult.payload.classOptions).find((entry) => (
      entry.spec.websimClassKey === safeDecode(router.params['classKey'])
      && entry.spec.websimSpecKey === safeDecode(router.params['specKey'])
    ))
    const selection = findSpecSelection(homeResult.payload, selectedSpecId || keyMatch?.spec.id || defaultSpecId)
    if (!selection) throw new Error('没有可用的职业专精映射')
    return {
      payload: {
        home: homeResult.payload,
        selection,
        talentTemplates: talentsResult.payload.templates,
        gearTemplates: gearResult.payload.templates,
        tasks: tasksResult.fromFallback ? [] : tasksResult.payload.tasks,
      },
      fromFallback: homeResult.fromFallback || tasksResult.fromFallback,
      error: [homeResult.error, tasksResult.error].filter(Boolean).join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
    void route.load()
  }, [selectedSpecId, route.load])

  useEffect(() => {
    if (!route.data) return
    const talents = compatibleTemplates(route.data.talentTemplates, route.data.selection)
    const gear = compatibleTemplates(route.data.gearTemplates, route.data.selection)
    setTalentTemplateId((current) => talents.some((item) => item.id === current) ? current : talents[0]?.id || '')
    setGearTemplateId((current) => gear.some((item) => item.id === current) ? current : gear[0]?.id || '')
  }, [route.data])

  const data = route.data
  const talentTemplates = compatibleTemplates(data?.talentTemplates ?? [], data?.selection)
  const gearTemplates = compatibleTemplates(data?.gearTemplates ?? [], data?.selection)
  const talentTemplate = talentTemplates.find((template) => template.id === talentTemplateId)
  const gearTemplate = gearTemplates.find((template) => template.id === gearTemplateId)
  const activeTasks = data?.tasks.filter(activeTask) ?? []
  const canPrepare = route.state.state === 'ready'
    && Boolean(talentTemplate && gearTemplate)
    && activeTasks.length === 0

  const invalidateConfirmation = () => {
    setConfirmation({ state: 'unknown' })
    setSubmittedTaskId('')
  }

  const buildRequest = (): Readonly<Record<string, unknown>> | null => {
    if (!data || !talentTemplate || !gearTemplate) return null
    return {
      mode: 'simcraft_template',
      confirmOnly: true,
      saveTask: false,
      classKey: data.selection.classKey,
      specKey: data.selection.specKey,
      raceKey: races[raceIndex]?.id ?? 'human',
      scenarioKey: scenarioOptions[scenarioIndex]?.key ?? 'single',
      durationSeconds: durations[durationIndex] ?? 300,
      analysisType: 'simcraft',
      templateContext: {
        talent: {
          id: talentTemplate.id,
          rawString: talentTemplate.rawString,
          source: talentTemplate.source,
        },
        gear: {
          id: gearTemplate.id,
          rawString: gearTemplate.rawString,
          source: gearTemplate.source,
          metadata: gearTemplate.metadata,
        },
      },
    }
  }

  const confirm = async () => {
    const request = buildRequest()
    if (!request || !canPrepare || !gearTemplate || !talentTemplate) return
    const gearBySlot = parsedGear(gearTemplate)
    if (!gearBySlot) {
      setConfirmation({ state: 'blocked', error: '装备模板不是可校验的结构化快照。' })
      return
    }
    setConfirmation({ state: 'loading' })
    try {
      const statsResult = await wowApi.websim.gearStats({
        classKey: data?.selection.classKey ?? '',
        specKey: data?.selection.specKey ?? '',
        talents: talentTemplate.rawString,
        gearBySlot,
        scenarioKey: scenarioOptions[scenarioIndex]?.key ?? 'single',
      })
      if (statsResult.fromFallback || statsResult.payload.statStatus === 'blocked') {
        setConfirmation({
          state: 'blocked',
          error: statsResult.error || statsResult.payload.blockers.join(' / ') || '装备属性校验未通过',
        })
        return
      }
      const result = await wowApi.simulator.analyze(request)
      if (result.fromFallback || !explicitValidationPassed(result.payload)) {
        setConfirmation({
          state: 'blocked',
          error: result.error || '后端没有明确返回 validation.passed=true',
          response: result.payload,
          stats: statsResult.payload,
        })
        return
      }
      setConfirmation({ state: 'ready', request, response: result.payload, stats: statsResult.payload })
    } catch (error) {
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
  const gearSlot = simcTemplateSlot('gear', gearTemplates, gearTemplateId)
  const modelInput = {
    specializationLabel: data?.selection.label ?? '',
    raceLabel: races[raceIndex]?.label ?? '未选择',
    scenarioLabel: scenarioOptions[scenarioIndex]?.title ?? '',
    durationSeconds: durations[durationIndex] ?? 300,
    ...(talentTemplate ? { talentTemplate } : {}),
    ...(gearTemplate ? { gearTemplate } : {}),
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
              races={races}
              selectedRaceIndex={raceIndex}
              selectedSpecializationId={data?.selection.specId ?? selectedSpecId}
              specializations={specializationItems}
              onRaceSelect={(index) => {
                setRaceIndex(index)
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
            <SimcTemplateSlot
              {...gearSlot}
              loading={loading}
              onSelect={(index) => {
                const next = gearTemplates[index]
                if (!next) return
                setGearTemplateId(next.id)
                invalidateConfirmation()
              }}
            />
          </RouteRegion>
          <RouteRegion className={styles['combatRegion'] ?? ''} data-region="combat_parameters">
            <SimcCombatConfiguration
              buffRules={simcBuffRules}
              durations={durations}
              scenarios={scenarioOptions.map((scenario) => ({ id: scenario.key, label: scenario.title }))}
              selectedDurationIndex={durationIndex}
              selectedScenarioIndex={scenarioIndex}
              onDurationSelect={(index) => {
                setDurationIndex(index)
                invalidateConfirmation()
              }}
              onScenarioSelect={(index) => {
                setScenarioIndex(index)
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
