import { Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import styles from './BuildsHomeCommandDeck.module.scss'

export interface BuildRecentSimcTaskItem {
  id: string
  title: string
  detail: string
  state: 'queued' | 'running' | 'failed' | 'completed' | 'unknown'
  stateLabel: string
  timeLabel: string
  navigable: boolean
}

export interface BuildRecentSimcTasksProps {
  items: readonly BuildRecentSimcTaskItem[]
  state: 'loading' | 'ready' | 'empty' | 'error'
  errorDetail?: string
  onRetry: () => void
  onSelect: (id: string) => void
}

function componentStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

function stateGlyph(state: BuildRecentSimcTaskItem['state']): 'utility-glyph-family.records' | 'utility-glyph-family.runtime' | 'utility-glyph-family.warning' | 'utility-glyph-family.shield' | 'utility-glyph-family.topic' {
  if (state === 'queued') return 'utility-glyph-family.records'
  if (state === 'running') return 'utility-glyph-family.runtime'
  if (state === 'failed') return 'utility-glyph-family.warning'
  if (state === 'completed') return 'utility-glyph-family.shield'
  return 'utility-glyph-family.topic'
}

function blankRow(state: BuildRecentSimcTasksProps['state']): BuildRecentSimcTaskItem {
  if (state === 'loading') {
    return {
      id: '',
      title: '正在读取最近模拟',
      detail: '任务状态待返回',
      state: 'unknown',
      stateLabel: '加载中',
      timeLabel: '请稍候',
      navigable: false,
    }
  }
  if (state === 'error') {
    return {
      id: '',
      title: '最近模拟暂不可用',
      detail: '可稍后重试读取任务记录',
      state: 'unknown',
      stateLabel: '暂不可用',
      timeLabel: '未返回时间',
      navigable: false,
    }
  }
  return {
    id: '',
    title: '暂无 SimC 任务',
    detail: '提交模拟后会在这里显示最近记录',
    state: 'unknown',
    stateLabel: '暂无记录',
    timeLabel: '未返回时间',
    navigable: false,
  }
}

export function BuildRecentSimcTasks({
  items,
  state,
  errorDetail,
  onRetry,
  onSelect,
}: BuildRecentSimcTasksProps): JSX.Element {
  const rows = state === 'ready'
    ? items
    : state === 'loading'
      ? [blankRow('loading'), blankRow('loading'), blankRow('loading')]
      : [blankRow(state)]

  return (
    <View className={componentStyle('recentSimcTasks')} data-owner="build-recent-simc-tasks" data-state={state}>
      <View className={componentStyle('recentSimcHeading')}>
        <View className={componentStyle('recentSimcHeadingGlyph')}>
          <SystemGlyph assetId="utility-glyph-family.records" slotId="asset_slot.utility-glyph-family" />
        </View>
        <Text>最近模拟</Text>
      </View>
      <View className={componentStyle('recentSimcRows')} data-state={state}>
        {rows.map((item, index) => (
          <ControlButton
            key={item.id || `${state}-${index}`}
            className={componentStyle('recentSimcRow')}
            data-disabled={item.navigable ? 'false' : 'true'}
            data-role="build-recent-simc-row"
            data-state={item.state}
            disabled={!item.navigable}
            onClick={() => item.id && onSelect(item.id)}
          >
            <View className={componentStyle('recentSimcRowGlyph')}>
              <SystemGlyph assetId={stateGlyph(item.state)} slotId="asset_slot.utility-glyph-family" />
            </View>
            <View className={componentStyle('recentSimcRowCopy')}>
              <Text>{item.title}</Text>
              <Text>{item.detail}</Text>
            </View>
            <View className={componentStyle('recentSimcRowMeta')}>
              <Text>{item.stateLabel}</Text>
              <Text>{item.timeLabel}</Text>
            </View>
            {item.navigable ? (
              <SystemGlyph
                assetId="utility-glyph-family.chevron-right"
                className={componentStyle('recentSimcChevron')}
                slotId="asset_slot.utility-glyph-family"
              />
            ) : null}
          </ControlButton>
        ))}
        {state === 'error' ? (
          <ControlButton
            className={componentStyle('recentSimcRetry')}
            data-role="build-recent-simc-retry"
            onClick={onRetry}
          >
            <Text>{errorDetail ? '重试读取' : '重试'}</Text>
          </ControlButton>
        ) : null}
      </View>
    </View>
  )
}
