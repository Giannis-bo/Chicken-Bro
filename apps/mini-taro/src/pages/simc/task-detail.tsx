import MiniSimcTaskId from '../../components/MiniSimcTaskId'
import MiniSimcReport from '../../components/MiniSimcReport'
import { simcDiagnosticMessage } from '../../features/simc/simc-messages'
import { simcStatuses, simcNameStatus } from '../../features/simc/simc-terms'
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
  const [detailsOpen, setDetailsOpen] = useState(false)
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
    if ((isTestLoginEnabled() || sessions.getValid()) && jobId.current) void loginAndPoll()
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
          <Text className={styles['eyebrow'] ?? ''}>Simc模拟</Text>
          <Text className={styles['title'] ?? ''}>模拟报告</Text>
        </View>
        <View className={styles['headerActions'] ?? ''}>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void Taro.navigateBack()}>
            返回
          </Button>
        </View>
      </View>

      {job ? (
        <ScrollView className={styles['content'] ?? ''} scrollY>
          <View className={styles['card'] ?? ''}>
            <Text className={styles['cardTitle'] ?? ''}>{simcStatuses[job.status]}</Text>
            <MiniSimcTaskId id={job.id} />
            <Text className={styles['hint'] ?? ''}>{job.status === 'queued' ? '任务已排队，轮到后会自动开始。可以返回，稍后从记录继续查看。' : job.status === 'running' ? '云端正在模拟，进度会自动更新。离开此页不会中断任务。' : job.status === 'succeeded' ? '模拟已完成，下方查看结果。' : job.status === 'cancelled' ? '任务已取消，未生成结果。' : '本次模拟未完成，可返回检查角色资料后重新提交。'}</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{simcDiagnosticMessage(job.errorCode)}</Text> : null}
          </View>
          <MiniSimcReport key={job.id} job={job} />
          <Button className={styles['secondaryButton'] ?? ''} onClick={() => void loginAndPoll()}>刷新状态</Button>
          <Button className={styles['secondaryButton'] ?? ''} onClick={() => setDetailsOpen(!detailsOpen)}>{detailsOpen ? '收起运行详情' : '查看运行详情'}</Button>
          {detailsOpen ? <>
          <View className={styles['card'] ?? ''}>
            {report?.localization ? <Text className={styles['meta'] ?? ''}>{simcNameStatus(report)} · 名称数据校验 {report.localization.catalogRevision || '不可用'}</Text> : null}
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

          {result ? <View className={styles['card'] ?? ''}>
              <Text className={styles['meta'] ?? ''}>角色配置校验：{result.profileSha256}</Text>
              <Text className={styles['meta'] ?? ''}>运行版本：{result.runtimeRevision}</Text>
              <Text className={styles['meta'] ?? ''}>来源版本：{result.provenance.sourceRevision}</Text>
              <Text className={styles['meta'] ?? ''}>场景校验：{result.provenance.scenarioHash}</Text>
          </View> : null}
          </> : null}
        </ScrollView>
      ) : null}

      {!job && state.phase !== 'blocked' && state.phase !== 'signed_out' ? (
        <View className={styles['loading'] ?? ''}><Text>{jobId.current ? '正在读取任务…' : '缺少任务信息，请返回任务记录重新打开。'}</Text></View>
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

export default withMiniTestLogin(SimcTaskDetailPage, false)
