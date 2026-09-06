import { simcDiagnosticMessage } from '../../features/simc/simc-messages'
import { simcStatuses } from '../../features/simc/simc-terms'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import Taro, { useDidShow } from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './tasks.module.scss'


function SimcTasksPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext()),
    [sessions],
  )
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
          <Text className={styles['eyebrow'] ?? ''}>云端任务记录</Text>
          <Text className={styles['title'] ?? ''}>模拟任务记录</Text>
        </View>
        <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void Taro.navigateBack()}>
          返回
        </Button>
      </View>

      <ScrollView className={styles['list'] ?? ''} scrollY>
        {state.jobs.map((job) => (
          <Button
            key={job.id}
            className={styles['jobCard'] ?? ''}
            data-status={job.status}
            onClick={() => void Taro.navigateTo({
              url: `/pages/simc/task-detail?id=${encodeURIComponent(job.id)}`,
            })}
          >
            <View className={styles['jobTopline'] ?? ''}>
              <Text className={styles['jobStatus'] ?? ''}>{simcStatuses[job.status]}</Text>
              <Text className={styles['jobTime'] ?? ''}>{job.updatedAt}</Text>
            </View>
            <Text className={styles['jobId'] ?? ''}>{job.id}</Text>
            <Text className={styles['jobMeta'] ?? ''}>{job.runtimeRevision}</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{simcDiagnosticMessage(job.errorCode)}</Text> : null}
          </Button>
        ))}
        {state.jobs.length === 0 && state.phase === 'ready' ? (
          <View className={styles['empty'] ?? ''}><Text>当前账户还没有模拟任务。</Text></View>
        ) : null}
      </ScrollView>

      {state.nextCursor ? (
        <Button className={styles['secondaryButton'] ?? ''} onClick={() => void model.loadJobs(state.nextCursor ?? undefined)}>
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

export default withMiniTestLogin(SimcTasksPage)
