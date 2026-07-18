import type { BuildTemplate, ReadinessState } from '@wow-mini/domain'

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
  id: 'group' | 'consumable' | 'food' | 'preparation'
  label: string
  value: string
  state: 'partial' | 'blocked'
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
  durationSeconds: number
  talentTemplate?: BuildTemplate | undefined
  gearTemplate?: BuildTemplate | undefined
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

export const simcBuffRules: readonly SimcBuffRuleView[] = [
  { id: 'group', label: '团队 / 队伍增益', value: '由后端按专精规则处理', state: 'partial' },
  { id: 'consumable', label: '药水与合剂', value: '未提供可验证输入', state: 'blocked' },
  { id: 'food', label: '食物与符文', value: '未提供可验证输入', state: 'blocked' },
  { id: 'preparation', label: '其他准备', value: '未经验证不写入 profile', state: 'blocked' },
]

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
      value: input.scenarioLabel || '未选择',
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
      value: '后端规则 · 手动配置未开放',
      state: 'partial',
    },
    {
      id: 'gear',
      label: '装备模板',
      value: input.gearTemplate?.title || '未选择',
      state: templateState(input.gearTemplate),
    },
    {
      id: 'preparation',
      label: '其他准备',
      value: `${input.durationSeconds} 秒 · 确认时校验`,
      state: input.confirmationState === 'ready' ? 'ready' : 'unknown',
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
      detail: input.scenarioLabel ? `${input.scenarioLabel} / ${input.durationSeconds} 秒` : '场景会影响确认请求',
      blocked: !input.scenarioLabel,
    },
    {
      id: 'talent',
      label: input.talentTemplate ? '天赋模板已选择' : '尚未选择天赋模板',
      detail: input.talentTemplate?.title || '不会生成默认模板',
      blocked: !input.talentTemplate,
    },
    {
      id: 'gear',
      label: input.gearTemplate ? '装备模板已选择' : '尚未选择装备模板',
      detail: input.gearTemplate?.title || '不会生成默认装备',
      blocked: !input.gearTemplate,
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
