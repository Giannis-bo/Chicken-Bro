import { simcDiagnosticMessage } from '../../features/simc/simc-messages'
import { simcStatuses, simcFightStyles, simcLabel, simcMetricName } from '../../features/simc/simc-terms'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import Taro, { useDidShow } from '@tarojs/taro'
import { Button, Picker, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import type { SimulationJobStatus } from '@wow-mini/domain'
import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './tasks.module.scss'


function SimcTasksPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext(), { workbench: true, localizedReport: true }),
    [sessions],
  )
  const statuses = ['all', 'queued', 'running', 'succeeded', 'failed', 'cancelled'] as const
  const [filter, setFilter] = useState<SimulationJobStatus | 'all'>('all')
  const [state, setState] = useState<SimcModelState>(() => model.get())

  useEffect(() => {
    const unsubscribe = model.subscribe((next) => {
      setState(next)
      if (isTestLoginEnabled() && next.phase === 'signed_out') sessions.invalidate()
    })
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model, sessions])

  const loginAndLoad = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      await model.loadJobs()
    } catch {
      await model.loadJobs()
    }
  }

  useEffect(() => {
    if (isTestLoginEnabled()) void loginAndLoad()
  }, [model, sessions])

  useDidShow(() => {
    void loginAndLoad()
  })

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>Simc模拟</Text>
          <Text className={styles['title'] ?? ''}>模拟任务记录</Text>
        </View>
        <View className={styles['headerActions'] ?? ''}>
          <Button className={styles['secondaryButton'] ?? ''} disabled={state.phase === 'loading'} onClick={() => void loginAndLoad()}>刷新任务</Button>
        </View>
      </View>

      <View className={styles['toolbar'] ?? ''}>
        <Picker data-field="taskStatus" mode="selector" range={statuses.map(s => s === 'all' ? '全部状态' : simcStatuses[s])} value={statuses.indexOf(filter)} onChange={e => setFilter(statuses[Number(e.detail.value)] ?? 'all')}>
          <View className={styles['filter'] ?? ''}>{filter === 'all' ? '全部状态' : simcStatuses[filter]} ▾</View>
        </Picker>
        <Text className={styles['loaded'] ?? ''}>已加载 {state.jobs.length} 项</Text>
      </View>
      {state.phase === 'loading' ? <Text className={styles['empty'] ?? ''}>正在读取任务…</Text> : null}
      <ScrollView className={styles['list'] ?? ''} scrollY>
        {state.jobs.filter(job => filter === 'all' || job.status === filter).map((job) => (
          <Button
            key={job.id}
            className={styles['jobCard'] ?? ''}
            data-status={job.status}
            data-job-id={job.id}
            onClick={() => void Taro.navigateTo({
              url: `/pages/simc/task-detail?id=${encodeURIComponent(job.id)}`,
            })}
          >
            <View className={styles['jobTopline'] ?? ''}>
              <Text className={styles['jobStatus'] ?? ''}>{simcStatuses[job.status]}</Text>
              <Text className={styles['jobTime'] ?? ''}>{new Date(job.updatedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</Text>
            </View>
            <Text className={styles['jobId'] ?? ''}>{job.character?.name || `模拟任务 · ${job.id.slice(0, 8)}`}</Text>
            <Text className={styles['jobMeta'] ?? ''}>{job.character ? `${simcLabel(job.character.specialization)} ${simcLabel(job.character.className)}` : '角色信息未记录'}</Text>
            <Text className={styles['jobMeta'] ?? ''}>{job.scenario ? `${simcFightStyles[job.scenario.fightStyle as keyof typeof simcFightStyles] || '战斗类型未记录'} · ${job.scenario.desiredTargets ?? '未记录'} 目标` : '配置未记录'}</Text>
            <Text className={styles['jobMetric'] ?? ''}>{job.metric ? `${job.metric.value.toLocaleString('zh-CN', {maximumFractionDigits: 2})} ${simcMetricName(job.metric.name)}` : job.status === 'queued' || job.status === 'running' ? '等待结果' : '无结果'}</Text>
            <Text className={styles['jobMeta'] ?? ''}>查看进度与结果 →</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{simcDiagnosticMessage(job.errorCode)}</Text> : null}
          </Button>
        ))}
        {!state.jobs.some(job => filter === 'all' || job.status === filter) && state.phase === 'ready' ? (
          <View className={styles['empty'] ?? ''}><Text>{filter === 'all' ? '还没有模拟记录。返回后读取角色，就能创建第一次模拟。' : '已加载记录中暂无此状态的任务，可切换状态或继续加载。'}</Text></View>
        ) : null}
      </ScrollView>

      {state.nextCursor ? (
        <Button className={styles['secondaryButton'] ?? ''} disabled={state.phase === 'loading'} onClick={() => void model.loadJobs(state.nextCursor ?? undefined)}>
          加载更多
        </Button>
      ) : null}
      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''}>
          <Text>{simcDiagnosticMessage(state.errorCode, state.errorMessage)}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void loginAndLoad()}>
            {state.phase === 'signed_out' ? '重新登录' : '重试'}
          </Button>
        </View>
      ) : null}
    </View>
  )
}

export default withMiniTestLogin(SimcTasksPage, false)
