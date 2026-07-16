import type { SimulatorTaskRecord } from '@wow-mini/domain'

export type TaskStatusGroup = 'queued' | 'running' | 'failed' | 'completed' | 'unknown'
export type TaskFilterId = 'all' | Exclude<TaskStatusGroup, 'unknown'>
export type TaskSortOrder = 'newest' | 'oldest'

export interface TaskSummaryMetricView {
  id: Exclude<TaskStatusGroup, 'unknown'>
  label: string
  count: number
}

export interface TaskRecordView {
  id: string
  title: string
  description: string
  tags: readonly [string, string, string]
  state: TaskStatusGroup
  stateLabel: string
  timeLabel: string
  feedback: string
  navigable: boolean
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function recordText(record: Readonly<Record<string, unknown>> | undefined, keys: readonly string[]): string {
  for (const key of keys) {
    const value = text(record?.[key])
    if (value) return value
  }
  return ''
}

export function taskStatusGroup(status: string): TaskStatusGroup {
  const value = status.trim().toLowerCase()
  if (value === 'queued') return 'queued'
  if (value === 'running' || value === 'processing') return 'running'
  if (['failed', 'error', 'canceled', 'cancelled', 'blocked'].includes(value)) return 'failed'
  if (['succeeded', 'completed', 'ready'].includes(value)) return 'completed'
  return 'unknown'
}

export function taskStatusLabel(status: string): string {
  const labels: Readonly<Record<TaskStatusGroup, string>> = {
    queued: '排队',
    running: '运行中',
    failed: '失败',
    completed: '已完成',
    unknown: '状态未知',
  }
  return labels[taskStatusGroup(status)]
}

export function taskSummaryMetrics(tasks: readonly SimulatorTaskRecord[]): readonly TaskSummaryMetricView[] {
  const counts: Record<Exclude<TaskStatusGroup, 'unknown'>, number> = {
    queued: 0,
    running: 0,
    failed: 0,
    completed: 0,
  }
  for (const task of tasks) {
    const group = taskStatusGroup(task.status)
    if (group !== 'unknown') counts[group] += 1
  }
  return [
    { id: 'queued', label: '排队', count: counts.queued },
    { id: 'running', label: '运行中', count: counts.running },
    { id: 'failed', label: '失败', count: counts.failed },
    { id: 'completed', label: '已完成', count: counts.completed },
  ]
}

function taskTimestamp(task: SimulatorTaskRecord): number {
  const value = task.updatedAt || task.createdAt || ''
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : 0
}

export function filterAndSortTasks(
  tasks: readonly SimulatorTaskRecord[],
  filter: TaskFilterId,
  order: TaskSortOrder,
): readonly SimulatorTaskRecord[] {
  return [...tasks]
    .filter((task) => filter === 'all' || taskStatusGroup(task.status) === filter)
    .sort((left, right) => order === 'newest'
      ? taskTimestamp(right) - taskTimestamp(left)
      : taskTimestamp(left) - taskTimestamp(right))
}

export function formatTaskTime(task: SimulatorTaskRecord): string {
  const value = task.updatedAt || task.createdAt || ''
  if (!value || !Number.isFinite(Date.parse(value))) return '未返回时间'
  const compact = value.replace('T', ' ').replace(/Z$/, '').slice(0, 16)
  return `${task.updatedAt ? '更新' : '创建'} ${compact}`
}

function modeLabel(mode: string | undefined): string {
  if (mode === 'simcraft_template') return 'SimC 模板任务'
  return mode ? `分析任务 · ${mode}` : '分析任务'
}

export function taskRecordView(task: SimulatorTaskRecord): TaskRecordView {
  const report = task.simcReportSummary
  const build = report?.build
  const scenario = report?.scenario
  const className = recordText(build, ['className'])
  const specName = recordText(build, ['specName'])
  const buildLabel = [className, specName].filter(Boolean).join(' / ') || '构筑未返回'
  const scenarioLabel = recordText(scenario, ['title', 'label', 'name', 'key']) || '场景未返回'
  const mode = modeLabel(task.mode)
  const state = taskStatusGroup(task.status)
  const description = text(report?.summary)
    || text(task.question)
    || text(report?.statusText)
    || '后端未返回任务摘要'
  const feedback = text(report?.statusText)
    || text(task.recommendations?.[0])
    || (state === 'failed' ? '后端未返回失败原因' : '')
  const id = task.taskId || task.id || ''
  return {
    id,
    title: text(report?.title) || mode,
    description,
    tags: [buildLabel, scenarioLabel, mode],
    state,
    stateLabel: taskStatusLabel(task.status),
    timeLabel: formatTaskTime(task),
    feedback,
    navigable: Boolean(id),
  }
}

export function latestTaskSummary(tasks: readonly SimulatorTaskRecord[]): { title: string; detail: string } {
  const latest = filterAndSortTasks(tasks, 'all', 'newest')[0]
  if (!latest) return { title: '暂无记录', detail: '当前 owner 未返回任务' }
  const view = taskRecordView(latest)
  return { title: view.title, detail: view.timeLabel }
}
