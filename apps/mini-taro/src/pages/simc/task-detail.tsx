import { simcDiagnosticMessage } from '../../features/simc/simc-messages'
import { simcMetricName, simcStatuses, simcReportName, simcNameStatus } from '../../features/simc/simc-terms'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import Taro, { useLoad } from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './task-detail.module.scss'


function SimcTaskDetailPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext(), { workbench: true, localizedReport: true }),
    [sessions],
  )
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const jobId = useRef(Taro.getCurrentInstance().router?.params['id'] ?? '')
  const cancelled = useRef(false)

  useEffect(() => {
    cancelled.current = false
    const unsubscribe = model.subscribe((next) => {
      setState(next)
      if (isTestLoginEnabled() && next.phase === 'signed_out') sessions.invalidate()
    })
    return () => {
      cancelled.current = true
      unsubscribe()
      model.dispose()
    }
  }, [model, sessions])

  const loginAndPoll = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      await model.pollJob(jobId.current, { cancelled: () => cancelled.current })
    } catch {
      await model.loadJob(jobId.current)
    }
  }

  useEffect(() => {
    if (isTestLoginEnabled() && jobId.current) void loginAndPoll()
  }, [model, sessions])

  useLoad<{ id?: string }>((params) => {
    jobId.current = typeof params.id === 'string' ? params.id.trim() : ''
    if (jobId.current) void loginAndPoll()
  })

  const job = state.activeJob
  const result = job?.result
  const report = result?.report

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase} data-job-status={job?.status ?? 'unknown'}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>模拟结果</Text>
          <Text className={styles['title'] ?? ''}>模拟任务详情</Text>
        </View>
        <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void Taro.navigateBack()}>
          返回
        </Button>
      </View>

      {job ? (
        <ScrollView className={styles['content'] ?? ''} scrollY>
          <View className={styles['card'] ?? ''}>
            <Text className={styles['cardTitle'] ?? ''}>状态：{simcStatuses[job.status]}</Text>
            <Text className={styles['meta'] ?? ''}>任务：{job.id}</Text>
            <Text className={styles['meta'] ?? ''}>编译器：{job.compilerRevision}</Text>
            <Text className={styles['meta'] ?? ''}>运行引擎：{job.runtimeRevision}</Text>
            <Text className={styles['meta'] ?? ''}>场景校验：{job.scenarioHash}</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{simcDiagnosticMessage(job.errorCode)}</Text> : null}
          </View>

          <View className={styles['card'] ?? ''}>
            <Text className={styles['cardTitle'] ?? ''}>执行尝试</Text>
            {job.attempts.map((attempt) => (
              <View key={`${attempt.attemptNumber}-${attempt.startedAt}`} className={styles['attempt'] ?? ''}>
                <Text>第 {attempt.attemptNumber} 次 · {simcDiagnosticMessage(attempt.diagnosticCode || (attempt.finishedAt ? '执行已结束' : 'RUNNING'))}</Text>
                <Text>{attempt.finishedAt || attempt.startedAt}</Text>
              </View>
            ))}
            {job.attempts.length === 0 ? <Text className={styles['hint'] ?? ''}>尚未开始云端执行。</Text> : null}
          </View>

          {result ? (
            <View className={styles['resultCard'] ?? ''}>
              <Text className={styles['resultMetric'] ?? ''}>{result.metricValue.toLocaleString()} {simcMetricName(result.metricName)}</Text>
              <Text className={styles['meta'] ?? ''}>角色配置校验：{result.profileSha256}</Text>
              <Text className={styles['meta'] ?? ''}>运行版本：{result.runtimeRevision}</Text>
              <Text className={styles['meta'] ?? ''}>来源版本：{result.provenance.sourceRevision}</Text>
              <Text className={styles['meta'] ?? ''}>场景校验：{result.provenance.scenarioHash}</Text>
            </View>
          ) : null}
          {report ? <>
            <View className={styles['card'] ?? ''}>
              <Text className={styles['cardTitle'] ?? ''}>技能贡献</Text>
              {report.localization && report.localization.status !== 'complete' ? <Text className={styles['hint'] ?? ''}>{simcNameStatus(report)}</Text> : null}
              {report.abilities.map((ability, index) => <View key={`${ability.name}-${index}`} className={styles['attempt'] ?? ''}>
                <Text>{simcReportName(report, 'abilities', index)}</Text>
                <Text>{ability.amount.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}{ability.portion == null ? '' : ` · ${ability.portion.toFixed(2)}%`}</Text>
              </View>)}
            </View>
            <View className={styles['card'] ?? ''}>
              <Text className={styles['cardTitle'] ?? ''}>增益覆盖</Text>
              {report.buffs.map((buff, index) => <View key={`${buff.name}-${index}`} className={styles['attempt'] ?? ''}>
                <Text>{simcReportName(report, 'buffs', index)}</Text><Text>{buff.uptime.toFixed(2)}%</Text>
              </View>)}
            </View>
          </> : null}
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

export default withMiniTestLogin(SimcTaskDetailPage)
