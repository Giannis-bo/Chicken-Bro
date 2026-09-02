import Taro, { useLoad } from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './task-detail.module.scss'


export default function SimcTaskDetailPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext()),
    [sessions],
  )
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const jobId = useRef('')
  const cancelled = useRef(false)

  useEffect(() => {
    cancelled.current = false
    const unsubscribe = model.subscribe(setState)
    return () => {
      cancelled.current = true
      unsubscribe()
    }
  }, [model])

  const loginAndPoll = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      await model.pollJob(jobId.current, { cancelled: () => cancelled.current })
    } catch {
      await model.loadJob(jobId.current)
    }
  }

  useLoad<{ id?: string }>((params) => {
    jobId.current = typeof params.id === 'string' ? params.id.trim() : ''
    if (jobId.current) void loginAndPoll()
  })

  const job = state.activeJob
  const result = job?.result

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase} data-job-status={job?.status ?? 'unknown'}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>SEMANTIC RESULT</Text>
          <Text className={styles['title'] ?? ''}>SimC 任务详情</Text>
        </View>
        <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void Taro.navigateBack()}>
          返回
        </Button>
      </View>

      {job ? (
        <ScrollView className={styles['content'] ?? ''} scrollY>
          <View className={styles['card'] ?? ''}>
            <Text className={styles['cardTitle'] ?? ''}>状态：{job.status}</Text>
            <Text className={styles['meta'] ?? ''}>任务：{job.id}</Text>
            <Text className={styles['meta'] ?? ''}>Compiler：{job.compilerRevision}</Text>
            <Text className={styles['meta'] ?? ''}>Runtime：{job.runtimeRevision}</Text>
            <Text className={styles['meta'] ?? ''}>Scenario：{job.scenarioHash}</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{job.errorCode}</Text> : null}
          </View>

          <View className={styles['card'] ?? ''}>
            <Text className={styles['cardTitle'] ?? ''}>执行尝试</Text>
            {job.attempts.map((attempt) => (
              <View key={`${attempt.attemptNumber}-${attempt.startedAt}`} className={styles['attempt'] ?? ''}>
                <Text>第 {attempt.attemptNumber} 次 · {attempt.diagnosticCode || 'RUNNING'}</Text>
                <Text>{attempt.finishedAt || attempt.startedAt}</Text>
              </View>
            ))}
            {job.attempts.length === 0 ? <Text className={styles['hint'] ?? ''}>尚未开始 Worker 尝试。</Text> : null}
          </View>

          {result ? (
            <View className={styles['resultCard'] ?? ''}>
              <Text className={styles['resultMetric'] ?? ''}>{result.metricValue.toLocaleString()} {result.metricName.toUpperCase()}</Text>
              <Text className={styles['meta'] ?? ''}>profileSha256：{result.profileSha256}</Text>
              <Text className={styles['meta'] ?? ''}>runtimeRevision：{result.runtimeRevision}</Text>
              <Text className={styles['meta'] ?? ''}>sourceRevision：{result.provenance.sourceRevision}</Text>
              <Text className={styles['meta'] ?? ''}>scenarioHash：{result.provenance.scenarioHash}</Text>
            </View>
          ) : null}
        </ScrollView>
      ) : null}

      {!job && state.phase !== 'blocked' && state.phase !== 'signed_out' ? (
        <View className={styles['loading'] ?? ''}><Text>正在读取任务并等待终态…</Text></View>
      ) : null}
      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
          <Text>{state.errorMessage || '任务暂不可用'}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void loginAndPoll()}>
            {state.phase === 'signed_out' ? '重新登录' : '刷新任务'}
          </Button>
        </View>
      ) : null}
    </View>
  )
}
