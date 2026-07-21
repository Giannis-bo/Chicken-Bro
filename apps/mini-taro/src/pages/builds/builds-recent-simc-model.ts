import type { SimulatorTaskRecord } from '@wow-mini/domain'

import {
  filterAndSortTasks,
  taskRecordView,
  type TaskStatusGroup,
} from '../simulator/tasks-list-model'

export interface RecentSimcTaskPreview {
  id: string
  title: string
  detail: string
  state: TaskStatusGroup
  stateLabel: string
  timeLabel: string
  navigable: boolean
}

export function buildRecentSimcTaskPreviews(
  tasks: readonly SimulatorTaskRecord[],
): readonly RecentSimcTaskPreview[] {
  return filterAndSortTasks(
    tasks.filter((task) => task.mode === 'simcraft_template'),
    'all',
    'newest',
  ).slice(0, 3).map((task) => {
    const view = taskRecordView(task)
    return {
      id: view.id,
      title: view.tags[0],
      detail: view.tags[1],
      state: view.state,
      stateLabel: view.stateLabel,
      timeLabel: view.timeLabel,
      navigable: view.navigable,
    }
  })
}
