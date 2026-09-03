import Taro, { useDidShow } from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './tasks.module.scss'


export default function SimcTasksPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext()),
    [sessions],
  )
  const [state, setState] = useState<SimcModelState>(() => model.get())

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  const loginAndLoad = async () => {
    try {
      if (!sessions.getValid()) await sessions.login()
      await model.loadJobs()
    } catch {
      await model.loadJobs()
    }
  }

  useDidShow(() => {
    void loginAndLoad()
  })

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>SERVER HISTORY</Text>
          <Text className={styles['title'] ?? ''}>SimC 任务记录</Text>
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
              <Text className={styles['jobStatus'] ?? ''}>{job.status}</Text>
              <Text className={styles['jobTime'] ?? ''}>{job.updatedAt}</Text>
            </View>
            <Text className={styles['jobId'] ?? ''}>{job.id}</Text>
            <Text className={styles['jobMeta'] ?? ''}>{job.runtimeRevision}</Text>
            {job.errorCode ? <Text className={styles['errorCode'] ?? ''}>{job.errorCode}</Text> : null}
          </Button>
        ))}
        {state.jobs.length === 0 && state.phase === 'ready' ? (
          <View className={styles['empty'] ?? ''}><Text>当前账户还没有 SimC 任务。</Text></View>
        ) : null}
      </ScrollView>

      {state.nextCursor ? (
        <Button className={styles['secondaryButton'] ?? ''} onClick={() => void model.loadJobs(state.nextCursor ?? undefined)}>
          加载更多
        </Button>
      ) : null}
      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''}>
          <Text>{state.errorMessage}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void loginAndLoad()}>
            {state.phase === 'signed_out' ? '重新登录' : '重试'}
          </Button>
        </View>
      ) : null}
    </View>
  )
}
