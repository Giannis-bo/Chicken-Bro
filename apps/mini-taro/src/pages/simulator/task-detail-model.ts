import type { SimulatorTaskRecord } from '@wow-mini/domain'

export type TaskDetailStatus = 'queued' | 'running' | 'completed' | 'failed' | 'blocked' | 'unknown'
export type TaskDetailTone = 'neutral' | 'pending' | 'active' | 'success' | 'danger' | 'blocked' | 'verified'
export type TaskDetailResultState = 'loading' | 'pending' | 'completed' | 'failed' | 'unsupported' | 'blocked'
export type TaskProgressState = 'complete' | 'active' | 'waiting' | 'error'

export interface TaskDetailCellView {
  id: string
  label: string
  value: string
  detail: string
  tone: TaskDetailTone
}

export interface TaskProgressStepView {
  id: string
  label: string
  state: TaskProgressState
}

export interface TaskDetailRouteContext {
  phase: 'loading' | 'ready' | 'blocked'
  reason: string
  refreshing: boolean
}

export interface TaskDetailView {
  routePhase: TaskDetailRouteContext['phase']
  refreshing: boolean
  title: string
  description: string
  status: TaskDetailStatus
  statusLabel: string
  metadata: readonly TaskDetailCellView[]
  result: {
    state: TaskDetailResultState
    statusLabel: string
    metricLabel: string
    metricValue: string
    description: string
    progress: readonly TaskProgressStepView[]
  }
  context: readonly TaskDetailCellView[]
  scenario: readonly TaskDetailCellView[]
  attributes: readonly TaskDetailCellView[]
  attributeVerified: boolean
  attributeNotice: string
  preparation: readonly TaskDetailCellView[]
  preparationState: 'verified' | 'partial' | 'blocked' | 'unavailable'
  preparationNotice: string
  exception: {
    state: 'none' | 'failed' | 'blocked'
    title: string
    detail: string
  }
  attributeDetail: string
  preparationDetail: string
  exceptionDetail: string
}

type UnknownRecord = Readonly<Record<string, unknown>>

const unavailable = '未返回'

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function record(value: unknown): UnknownRecord {
  return isRecord(value) ? value : {}
}

function records(value: unknown): readonly UnknownRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function text(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

function firstText(...values: readonly unknown[]): string {
  for (const value of values) {
    const candidate = text(value)
    if (candidate) return candidate
  }
  return ''
}

function stringList(value: unknown): readonly string[] {
  return Array.isArray(value)
    ? value.map(text).filter((item) => item.length > 0)
    : []
}

function bounded(value: string, max = 52): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

function formatTimestamp(value: unknown): string {
  const source = text(value)
  if (!source || !Number.isFinite(Date.parse(source))) return unavailable
  return source.replace('T', ' ').replace(/Z$/, '').slice(0, 16)
}

function formatDuration(value: unknown): string {
  const milliseconds = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return unavailable
  if (milliseconds < 1_000) return `${Math.round(milliseconds)} ms`
  const seconds = Math.round(milliseconds / 1_000)
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分`
}

function statusGroup(status: string): TaskDetailStatus {
  const value = status.toLowerCase().trim()
  if (value === 'queued') return 'queued'
  if (value === 'running' || value === 'processing') return 'running'
  if (value === 'succeeded' || value === 'completed' || value === 'ready') return 'completed'
  if (value === 'failed' || value === 'error') return 'failed'
  if (value === 'blocked' || value === 'canceled' || value === 'cancelled') return 'blocked'
  return 'unknown'
}

function statusLabel(status: TaskDetailStatus): string {
  const labels: Readonly<Record<TaskDetailStatus, string>> = {
    queued: '排队中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    blocked: '已阻断',
    unknown: '状态未知',
  }
  return labels[status]
}

function toneForStatus(status: TaskDetailStatus): TaskDetailTone {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'blocked') return 'blocked'
  if (status === 'running') return 'active'
  if (status === 'queued') return 'pending'
  return 'neutral'
}

function sourceLabel(mode: string): string {
  if (mode === 'simcraft_template') return 'SimC 模板'
  if (mode.toLowerCase().includes('warcraft') || mode.toLowerCase().includes('wcl')) return '战斗日志'
  return mode ? bounded(mode, 24) : unavailable
}

function displayValue(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return text(value) || unavailable
}

function cell(id: string, label: string, value: string, detail = '', tone: TaskDetailTone = 'neutral'): TaskDetailCellView {
  return { id, label, value: value || unavailable, detail, tone }
}

function reportFor(task: SimulatorTaskRecord | undefined): UnknownRecord {
  return record(task?.analysis?.simcReport)
}

function buildFor(task: SimulatorTaskRecord | undefined, report: UnknownRecord): UnknownRecord {
  const reportBuild = record(report['build'])
  if (Object.keys(reportBuild).length) return reportBuild
  return record(record(task?.request)['buildContext'])
}

function templateFor(task: SimulatorTaskRecord | undefined, kind: 'talent' | 'gear'): UnknownRecord {
  return record(record(record(task?.request)['templateContext'])[kind])
}

function progressFor(status: TaskDetailStatus, hasFormalResult: boolean): readonly TaskProgressStepView[] {
  const labels = [
    { id: 'submitted', label: '任务已提交' },
    { id: 'queued', label: '排队中' },
    { id: 'running', label: '模拟运行中' },
    { id: 'result', label: '结果生成中' },
  ] as const
  if (status === 'completed') return labels.map((step) => ({ ...step, state: 'complete' as const }))
  if (status === 'failed' || status === 'blocked') {
    return labels.map((step, index) => ({ ...step, state: index < 2 ? 'complete' as const : 'error' as const }))
  }
  if (status === 'running') {
    return labels.map((step, index) => ({ ...step, state: index < 2 ? 'complete' as const : index === 2 ? 'active' as const : 'waiting' as const }))
  }
  if (status === 'queued') {
    return labels.map((step, index) => ({ ...step, state: index === 0 ? 'complete' as const : index === 1 ? 'active' as const : 'waiting' as const }))
  }
  if (hasFormalResult) return labels.map((step) => ({ ...step, state: 'complete' as const }))
  return labels.map((step) => ({ ...step, state: 'waiting' as const }))
}

function metricValue(metric: UnknownRecord): string {
  return firstText(metric['convertedValue'], metric['value'], metric['convertedRawValue'], metric['rawValue']) || unavailable
}

function metricLabel(metric: UnknownRecord): string {
  return firstText(metric['label'], metric['key'])
}

function matchingMetric(metrics: readonly UnknownRecord[], keys: readonly string[]): UnknownRecord {
  return metrics.find((metric) => {
    const candidate = `${text(metric['key'])} ${text(metric['label'])}`.toLowerCase()
    return keys.some((key) => candidate.includes(key))
  }) ?? {}
}

function publicErrors(task: SimulatorTaskRecord | undefined, report: UnknownRecord, preparation: UnknownRecord): readonly string[] {
  const messages = record(report['messages'])
  const simulation = record(task?.analysis?.simulation)
  return [
    ...stringList(messages['blockers']),
    ...stringList(messages['errors']),
    ...stringList(preparation['blockers']),
    text(simulation['error']),
  ].filter((item) => item.length > 0)
}

export function buildTaskDetailView(
  task: SimulatorTaskRecord | undefined,
  route: TaskDetailRouteContext,
): TaskDetailView {
  const report = reportFor(task)
  const reportResult = record(report['result'])
  const build = buildFor(task, report)
  const scenario = record(report['scenario'])
  const timing = record(report['timing'])
  const request = record(task?.request)
  const preparation = record(report['preparation'])
  const rawStatus = firstText(task?.status, task?.analysis?.status, report['state'])
  const status = task ? statusGroup(rawStatus) : route.phase === 'blocked' ? 'blocked' : 'unknown'
  const profileSource = firstText(report['profileSource'], request['profileSource'])
  const generatedProfile = ['generated', 'preview'].includes(profileSource.toLowerCase())
  const dpsDisplay = text(reportResult['dpsDisplay'])
  const formalResult = task?.mode === 'simcraft_template'
    && reportResult['ran'] === true
    && reportResult['hasDps'] === true
    && Boolean(dpsDisplay)
    && !generatedProfile
  const nonSimc = Boolean(task && task.mode !== 'simcraft_template')

  let resultState: TaskDetailResultState = 'pending'
  if (!task && route.phase === 'loading') resultState = 'loading'
  else if (!task && route.phase === 'blocked') resultState = 'blocked'
  else if (nonSimc) resultState = 'unsupported'
  else if (status === 'failed') resultState = 'failed'
  else if (status === 'blocked') resultState = 'blocked'
  else if (formalResult) resultState = 'completed'
  else if (status === 'completed') resultState = 'unsupported'

  const reportSummary = firstText(report['summary'], report['statusText'])
  const resultDescription = resultState === 'completed'
    ? reportSummary || '后端返回了可核验的正式模拟结果'
    : resultState === 'loading'
      ? '正在读取当前 owner 的任务详情'
      : resultState === 'failed'
        ? '任务失败，结果数字不会展示'
        : resultState === 'blocked'
          ? route.reason || '任务详情当前不可用'
          : resultState === 'unsupported'
            ? nonSimc ? '此任务没有结构化 SimC 报告' : '任务已结束，但结果未满足正式展示条件'
            : '任务尚未返回可核验的正式结果'
  const resultStatus = resultState === 'completed'
    ? '正式结果'
    : resultState === 'failed'
      ? '任务失败'
      : resultState === 'blocked'
        ? '不可读取'
        : resultState === 'unsupported'
          ? '结果不可核验'
          : resultState === 'loading'
            ? '读取中'
            : statusLabel(status)

  const talentTemplate = record(build['talentTemplate'])
  const gearTemplate = record(build['gearTemplate'])
  const requestTalent = templateFor(task, 'talent')
  const requestGear = templateFor(task, 'gear')
  const simulation = record(task?.analysis?.simulation)
  const simcVersion = firstText(report['simcVersion'], reportResult['simcVersion'], simulation['simcVersion'], request['simcVersion'])
  const context = [
    cell('talent', '天赋构筑', firstText(talentTemplate['title'], talentTemplate['id'], requestTalent['title'], requestTalent['name'], requestTalent['id']) || unavailable),
    cell('version', 'SimC 版本', simcVersion || unavailable),
    cell('gear', '装备配置', firstText(gearTemplate['title'], gearTemplate['id'], requestGear['title'], requestGear['name'], requestGear['id']) || unavailable),
    cell('profile', '配置文件', profileSource || unavailable),
  ]

  const scenarioCells = [
    cell('scenario-type', '场景类型', firstText(scenario['label'], scenario['fightStyle'], scenario['key']) || unavailable, text(scenario['fightStyle'])),
    cell('duration', '战斗时长', text(scenario['durationSeconds']) ? `${text(scenario['durationSeconds'])} 秒` : unavailable),
    cell('targets', '目标数量', displayValue(scenario['targets'])),
    cell('enemy-level', '敌人等级', firstText(scenario['enemyLevel'], scenario['level']) || unavailable),
  ]

  const snapshot = record(build['statSnapshot'])
  const verifiedStats = snapshot['statStatus'] === 'verified'
  const primaryMetric = record(snapshot['primary'])
  const secondaryMetrics = records(snapshot['secondary'])
  const allMetrics = [primaryMetric, ...secondaryMetrics].filter((metric) => Object.keys(metric).length > 0)
  const physicalMetrics = [
    { id: 'strength', label: '力量', keys: ['strength', '力量'] },
    { id: 'agility', label: '敏捷', keys: ['agility', '敏捷'] },
    { id: 'intellect', label: '智力', keys: ['intellect', 'intelligence', '智力'] },
    { id: 'stamina', label: '耐力', keys: ['stamina', '耐力'] },
  ] as const
  const attributeCells: TaskDetailCellView[] = physicalMetrics.map((definition) => {
    const metric = verifiedStats ? matchingMetric(allMetrics, definition.keys) : {}
    return cell(definition.id, definition.label, metricValue(metric), metricLabel(metric), verifiedStats && Object.keys(metric).length ? 'verified' : 'neutral')
  })
  attributeCells.push(
    cell('primary', '主属性', verifiedStats ? metricValue(primaryMetric) : unavailable, metricLabel(primaryMetric), verifiedStats ? 'verified' : 'neutral'),
    cell(
      'secondary',
      '副属性',
      verifiedStats && secondaryMetrics.length
        ? secondaryMetrics.slice(0, 4).map((metric) => `${metricLabel(metric) || '属性'} ${metricValue(metric)}`).join(' / ')
        : unavailable,
      verifiedStats ? text(snapshot['statSource']) : '',
      verifiedStats ? 'verified' : 'neutral',
    ),
  )

  const preparationItems = records(preparation['items'])
  const itemFor = (category: string): UnknownRecord => preparationItems.find((item) => text(item['category']) === category) ?? {}
  const preparationCell = (id: string, label: string, category: string): TaskDetailCellView => {
    const item = itemFor(category)
    const value = firstText(item['label'], item['state']) || unavailable
    const evidence = text(item['evidenceState'])
    return cell(id, label, value, firstText(item['summary'], item['state']), evidence === 'verified' ? 'verified' : evidence === 'partial' ? 'pending' : evidence === 'blocked' ? 'blocked' : 'neutral')
  }
  const evidenceState = text(preparation['evidenceState'])
  const preparationState = evidenceState === 'verified'
    ? 'verified'
    : evidenceState === 'partial'
      ? 'partial'
      : evidenceState === 'blocked'
        ? 'blocked'
        : 'unavailable'
  const preparationCells = [
    preparationCell('raid-baseline', '团队基线', 'raid_buff_baseline'),
    preparationCell('class-buff', '职业增益', 'self_class_raid_buff'),
    preparationCell('spec-preparation', '专精准备', 'spec_combat_preparation'),
    preparationCell('temporary-buffs', '临时增益', 'temporary_combat_buffs'),
    cell('evidence-state', '证据状态', evidenceState || unavailable, text(preparation['summary']), preparationState === 'verified' ? 'verified' : preparationState === 'partial' ? 'pending' : preparationState === 'blocked' ? 'blocked' : 'neutral'),
  ]

  const errors = publicErrors(task, report, preparation)
  const exceptionState = route.phase === 'blocked' || status === 'blocked'
    ? 'blocked'
    : status === 'failed'
      ? 'failed'
      : 'none'
  const exceptionDetail = route.phase === 'blocked'
    ? route.reason || '任务详情当前不可用'
    : errors[0] || (exceptionState === 'none' ? '当前没有后端返回的异常' : '后端未返回失败原因')

  const mode = text(task?.mode)
  const title = firstText(report['title'], task?.question, mode ? sourceLabel(mode) : '') || (route.phase === 'loading' ? '正在读取任务' : '任务详情不可用')
  const description = reportSummary || firstText(task?.recommendations?.[0]) || (task ? '后端未返回任务摘要' : route.reason || '等待后端返回当前 owner 的任务')
  const metadata = [
    cell('created', '创建时间', formatTimestamp(task?.createdAt), '', toneForStatus(status)),
    cell('started', '开始时间', formatTimestamp(timing['startedAt'])),
    cell('elapsed', '运行时长', formatDuration(timing['elapsedMs'])),
    cell('source', '任务来源', sourceLabel(mode)),
  ]

  const attributeDetail = attributeCells.map((item) => `${item.label}：${item.value}${item.detail ? `（${item.detail}）` : ''}`).join('\n')
  const preparationDetail = preparationCells.map((item) => `${item.label}：${item.value}${item.detail ? `\n${item.detail}` : ''}`).join('\n')

  return {
    routePhase: route.phase,
    refreshing: route.refreshing,
    title: bounded(title, 40),
    description: bounded(description, 90),
    status,
    statusLabel: statusLabel(status),
    metadata,
    result: {
      state: resultState,
      statusLabel: resultStatus,
      metricLabel: formalResult ? firstText(reportResult['metricLabel'], 'DPS') : 'SimC 结果',
      metricValue: formalResult ? dpsDisplay : unavailable,
      description: resultDescription,
      progress: progressFor(status, formalResult),
    },
    context,
    scenario: scenarioCells,
    attributes: attributeCells,
    attributeVerified: verifiedStats,
    attributeNotice: verifiedStats ? '属性快照来自后端已核验数据' : '后端未返回已核验属性快照',
    preparation: preparationCells,
    preparationState,
    preparationNotice: text(preparation['summary']) || '后端未返回战斗准备配置',
    exception: {
      state: exceptionState,
      title: exceptionState === 'none' ? '当前无异常' : exceptionState === 'blocked' ? '任务不可读取' : '任务执行失败',
      detail: bounded(exceptionDetail, 100),
    },
    attributeDetail,
    preparationDetail,
    exceptionDetail: errors.length ? errors.join('\n') : exceptionDetail,
  }
}
