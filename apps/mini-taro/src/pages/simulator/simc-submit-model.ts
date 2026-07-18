import type {
  BuildTemplate,
  GearSelectionIntent,
  ReadinessState,
  SimcOptionsPayload,
  SimcPreparationOption,
  SimcProfileContext,
} from '@wow-mini/domain'
import { canonicalGearSelectionIntent } from '@wow-mini/domain'

export type SimcTruthState = 'ready' | 'partial' | 'blocked' | 'unknown'

export interface SimcTemplateSlotView {
  type: 'talent' | 'gear'
  title: string
  sourceLabel: string
  valueLabel: string
  helperLabel: string
  state: SimcTruthState
  selectedIndex: number
  options: readonly string[]
}

export interface SimcBuffRuleView {
  id: string
  label: string
  value: string
  state: 'ready' | 'partial' | 'blocked'
  overrideSupported?: boolean
}

export interface SimcOptionsView {
  state: 'ready' | 'empty' | 'blocked'
  races: readonly { id: string; label: string }[]
  scenarios: readonly { id: string; label: string }[]
  selectedRaceKey: string
  selectedRaceIndex: number
  selectedScenarioKey: string
  selectedScenarioIndex: number
  durationSeconds: number | undefined
  targets: number | undefined
  preparationRows: readonly SimcPreparationOption[]
}

export interface CanonicalSimcContext {
  selectionIntent: GearSelectionIntent
  profileContext: SimcProfileContext
}

export interface SimcSubmissionToken {
  readonly inputRevision: number
  readonly operationRevision: number
}

export interface SimcSubmissionSession {
  begin: () => SimcSubmissionToken
  invalidate: () => void
  mount: () => void
  unmount: () => void
  isCurrent: (token: SimcSubmissionToken) => boolean
}

export interface SimcSummaryRowView {
  id: string
  label: string
  value: string
  state: SimcTruthState
}

export interface SimcBlockerRowView {
  id: string
  label: string
  detail: string
  blocked: boolean
}

export interface SimcSubmitModelInput {
  specializationLabel: string
  raceLabel: string
  scenarioLabel: string
  scenarioTargets?: number | undefined
  durationSeconds?: number | undefined
  talentTemplate?: BuildTemplate | undefined
  gearContextAvailable?: boolean | undefined
  gearContextLabel?: string | undefined
  preparationLabel?: string | undefined
  preparationState?: 'ready' | 'partial' | 'blocked' | undefined
  activeTaskCount: number
  confirmationState: ReadinessState
  confirmationError?: string | undefined
}

export function simcTemplateSlot(
  type: 'talent' | 'gear',
  templates: readonly BuildTemplate[],
  selectedId: string,
): SimcTemplateSlotView {
  const selectedIndex = Math.max(0, templates.findIndex((template) => template.id === selectedId))
  const selected = templates.find((template) => template.id === selectedId)
  const title = type === 'talent' ? '天赋模板' : '装备模板'
  const sourceLabel = type === 'talent' ? '来自天赋构筑' : '来自装备详情'
  if (!selected) {
    return {
      type,
      title,
      sourceLabel,
      valueLabel: `未选择${title}`,
      helperLabel: templates.length ? `有 ${templates.length} 个可用模板` : '尚未保存模板',
      state: 'blocked',
      selectedIndex,
      options: templates.map((template) => template.title),
    }
  }
  return {
    type,
    title,
    sourceLabel,
    valueLabel: selected.title,
    helperLabel: selected.remote ? '账户已同步' : '仅保存在本机',
    state: selected.remote ? 'ready' : 'partial',
    selectedIndex,
    options: templates.map((template) => template.title),
  }
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function simcRouteFromFallback(input: {
  homeFromFallback: boolean
  optionsFromFallback: boolean
  talentsFromFallback: boolean
  tasksFromFallback: boolean
}): boolean {
  return input.homeFromFallback || input.optionsFromFallback || input.tasksFromFallback
}

export function simcCanPrepare(input: {
  routeState: ReadinessState
  optionsState: SimcOptionsView['state']
  canonicalContextAvailable: boolean
  activeTaskCount: number
  submitting: boolean
}): boolean {
  return input.routeState === 'ready'
    && input.optionsState === 'ready'
    && input.canonicalContextAvailable
    && input.activeTaskCount === 0
    && !input.submitting
}

export function createSimcSubmissionSession(): SimcSubmissionSession {
  let mounted = true
  let inputRevision = 0
  let operationRevision = 0
  return {
    begin() {
      operationRevision += 1
      return { inputRevision, operationRevision }
    },
    invalidate() {
      inputRevision += 1
      operationRevision += 1
    },
    mount() {
      mounted = true
      inputRevision += 1
      operationRevision += 1
    },
    unmount() {
      mounted = false
      inputRevision += 1
      operationRevision += 1
    },
    isCurrent(token) {
      return mounted
        && token.inputRevision === inputRevision
        && token.operationRevision === operationRevision
    },
  }
}

export function canonicalSimcBuildIntent(
  buildContext: unknown,
  classKey: string,
  specKey: string,
): GearSelectionIntent | null {
  if (!isRecord(buildContext)
    || buildContext['classKey'] !== classKey
    || buildContext['specKey'] !== specKey) return null
  return canonicalGearSelectionIntent(buildContext['selectionIntent'], classKey, specKey)
}

export function deriveSimcOptionsView(
  options: SimcOptionsPayload,
  classKey: string,
  specKey: string,
  preferredRaceKey: string,
  preferredScenarioKey: string,
): SimcOptionsView {
  const contractReady = options.contractRevision === 'simc-options-v1' && options.status === 'ready'
  const raceReady = contractReady && options.races.status === 'supported'
  const preparationReady = contractReady && options.preparation.status === 'ready'
  const supportedRaceKeys = raceReady
    ? options.races.supportedKeys.filter((key) => typeof key === 'string' && key.length > 0)
    : []
  const supportedScenarios = contractReady
    ? options.scenarios.filter((scenario) => scenario.status === 'supported')
    : []
  const classDefault = options.races.defaultByClass[classKey] ?? ''
  const selectedRaceKey = [preferredRaceKey, classDefault, options.races.defaultKey]
    .find((key) => supportedRaceKeys.includes(key))
    ?? supportedRaceKeys[0]
    ?? ''
  const selectedScenario = supportedScenarios.find((scenario) => scenario.key === preferredScenarioKey)
    ?? supportedScenarios[0]
  const preparationRows = preparationReady
    ? options.preparation.rows.filter((row) => (
      (!row.classKey || row.classKey === classKey)
      && (!row.specKey || row.specKey === specKey)
    ))
    : []
  const empty = supportedRaceKeys.length === 0
    || supportedScenarios.length === 0
    || preparationRows.length === 0

  return {
    state: !contractReady || !raceReady || !preparationReady ? 'blocked' : empty ? 'empty' : 'ready',
    races: supportedRaceKeys.map((key) => ({ id: key, label: key })),
    scenarios: supportedScenarios.map((scenario) => ({ id: scenario.key, label: scenario.label })),
    selectedRaceKey,
    selectedRaceIndex: Math.max(0, supportedRaceKeys.indexOf(selectedRaceKey)),
    selectedScenarioKey: selectedScenario?.key ?? '',
    selectedScenarioIndex: Math.max(
      0,
      supportedScenarios.findIndex((scenario) => scenario.key === selectedScenario?.key),
    ),
    durationSeconds: selectedScenario?.durationSeconds,
    targets: selectedScenario?.targets,
    preparationRows,
  }
}

export function buildCanonicalSimcContext(input: {
  buildContext: unknown
  classKey: string
  specKey: string
  raceKey: string
  scenarioKey: string
  talentTemplate: BuildTemplate | undefined
}): CanonicalSimcContext | null {
  const context = input.buildContext
  const template = input.talentTemplate
  const intent = canonicalSimcBuildIntent(context, input.classKey, input.specKey)
  if (!intent
    || !template
    || !input.raceKey
    || !input.scenarioKey) return null

  const rawTalent = template.rawString.trim()
  if (!rawTalent) return null
  const profileContext: SimcProfileContext = {
    classKey: input.classKey,
    specKey: input.specKey,
    race: input.raceKey,
    scenarioKey: input.scenarioKey,
    ...(template.heroKey ? { heroKey: template.heroKey } : {}),
    talents: rawTalent,
  }
  return {
    selectionIntent: intent,
    profileContext,
  }
}

function templateState(template: BuildTemplate | undefined): SimcTruthState {
  if (!template) return 'blocked'
  return template.remote ? 'ready' : 'partial'
}

export function simcSummaryRows(input: SimcSubmitModelInput): readonly SimcSummaryRowView[] {
  return [
    {
      id: 'identity',
      label: '职业 / 种族',
      value: `${input.specializationLabel} / ${input.raceLabel}`,
      state: input.specializationLabel ? 'ready' : 'blocked',
    },
    {
      id: 'scenario',
      label: '战斗场景',
      value: input.scenarioLabel
        ? `${input.scenarioLabel}${input.scenarioTargets ? ` · ${input.scenarioTargets} 目标` : ''}`
        : '未选择',
      state: input.scenarioLabel ? 'ready' : 'blocked',
    },
    {
      id: 'talent',
      label: '天赋模板',
      value: input.talentTemplate?.title || '未选择',
      state: templateState(input.talentTemplate),
    },
    {
      id: 'buffs',
      label: '战斗增益',
      value: input.preparationLabel || '后端未返回准备规则',
      state: input.preparationState || 'blocked',
    },
    {
      id: 'gear',
      label: '装备来源',
      value: input.gearContextLabel || '未带入',
      state: input.gearContextAvailable ? 'partial' : 'blocked',
    },
    {
      id: 'preparation',
      label: '其他准备',
      value: input.durationSeconds === undefined
        ? '后端未返回时长'
        : `${input.durationSeconds} 秒 · 确认时校验`,
      state: input.durationSeconds === undefined
        ? 'blocked'
        : input.confirmationState === 'ready' ? 'ready' : 'unknown',
    },
  ]
}

export function simcBlockerRows(input: SimcSubmitModelInput): readonly SimcBlockerRowView[] {
  const confirmationReady = input.confirmationState === 'ready'
  return [
    {
      id: 'identity',
      label: input.specializationLabel ? '职业、专精与种族已选择' : '尚未选择职业、专精与种族',
      detail: input.specializationLabel ? `${input.specializationLabel} / ${input.raceLabel}` : '需要真实职业专精映射',
      blocked: !input.specializationLabel,
    },
    {
      id: 'scenario',
      label: input.scenarioLabel ? '战斗场景与时长已选择' : '尚未选择战斗场景',
      detail: input.scenarioLabel && input.durationSeconds !== undefined
        ? `${input.scenarioLabel} / ${input.durationSeconds} 秒`
        : '场景及时长均以后端选项为准',
      blocked: !input.scenarioLabel || input.durationSeconds === undefined,
    },
    {
      id: 'talent',
      label: input.talentTemplate ? '天赋模板已选择' : '尚未选择天赋模板',
      detail: input.talentTemplate?.title || '不会生成默认模板',
      blocked: !input.talentTemplate,
    },
    {
      id: 'gear',
      label: input.gearContextAvailable
        ? 'canonical intent 已带入'
        : '尚未带入装备上下文',
      detail: input.gearContextAvailable
        ? `${input.gearContextLabel || '本机装备意图'}；等待本次后端快照校验`
        : '不会生成默认装备',
      blocked: !input.gearContextAvailable,
    },
    {
      id: 'validation',
      label: input.activeTaskCount
        ? `${input.activeTaskCount} 个任务正在处理`
        : confirmationReady
          ? '属性与后端确认已通过'
          : '尚未完成属性与后端确认',
      detail: input.confirmationError
        || (input.activeTaskCount ? '等待活动任务结束' : confirmationReady ? '后端已确认当前组合' : '先执行校验组合'),
      blocked: input.activeTaskCount > 0 || !confirmationReady,
    },
  ]
}

export function simcConfirmationLabel(
  state: ReadinessState,
  submitting: boolean,
  submittedTaskId: string,
): { title: string; detail: string; state: SimcTruthState } {
  if (submittedTaskId) return { title: '任务已提交', detail: submittedTaskId, state: 'ready' }
  if (submitting) return { title: '正在提交任务', detail: '等待后端返回 taskId', state: 'partial' }
  if (state === 'loading') return { title: '正在校验组合', detail: '先校验属性，再执行 confirmOnly', state: 'partial' }
  if (state === 'ready') return { title: '组合校验通过', detail: '可提交真实任务', state: 'ready' }
  if (state === 'blocked' || state === 'error') return { title: '组合校验未通过', detail: '查看阻断项后重试', state: 'blocked' }
  return { title: '等待组合校验', detail: '不会生成本地结果预览', state: 'unknown' }
}
