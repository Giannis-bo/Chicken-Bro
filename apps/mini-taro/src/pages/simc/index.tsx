import Taro, { useDidShow } from '@tarojs/taro'
import { Button, Input, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './index.module.scss'


export default function SimcPage() {
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext()),
    [sessions],
  )
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const [sourceUrl, setSourceUrl] = useState('')
  const [targets, setTargets] = useState('1')
  const [iterations, setIterations] = useState('300')

  useEffect(() => {
    const unsubscribe = model.subscribe(setState)
    return () => {
      unsubscribe()
      model.dispose()
    }
  }, [model])

  const ensureSession = async () => {
    if (!sessions.getValid()) await sessions.login()
  }

  useDidShow(() => {
    void ensureSession().catch(() => model.loadJobs())
  })

  const resolveSource = async () => {
    try {
      await ensureSession()
      await model.resolveSource(sourceUrl)
    } catch {
      await model.loadJobs()
    }
  }

  const submit = async () => {
    const job = await model.submitJob({
      fightStyle: 'Patchwerk',
      desiredTargets: Number(targets),
      iterations: Number(iterations),
    })
    if (job) {
      await Taro.navigateTo({ url: `/pages/simc/task-detail?id=${encodeURIComponent(job.id)}` })
    }
  }

  const relogin = () => {
    void sessions.logout().catch(() => undefined).finally(() => ensureSession())
  }

  const snapshot = state.snapshot

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>SIMULATIONCRAFT</Text>
          <Text className={styles['title'] ?? ''}>SimC 模拟</Text>
        </View>
        <Button
          className={styles['secondaryButton'] ?? ''}
          size="mini"
          onClick={() => void Taro.navigateTo({ url: '/pages/simc/tasks' })}
        >
          任务记录
        </Button>
      </View>

      <View className={styles['card'] ?? ''}>
        <Text className={styles['cardTitle'] ?? ''}>1. 读取角色来源</Text>
        <Text className={styles['hint'] ?? ''}>仅接受 Raider.IO 或 Warcraft Logs 的 HTTPS 角色链接。</Text>
        <Input
          className={styles['input'] ?? ''}
          placeholder="粘贴 Raider.IO / WCL 链接"
          value={sourceUrl}
          onInput={(event) => setSourceUrl(event.detail.value)}
        />
        <Button
          className={styles['primaryButton'] ?? ''}
          disabled={!sourceUrl.trim() || state.phase === 'loading'}
          loading={state.phase === 'loading'}
          onClick={() => void resolveSource()}
        >
          检查角色快照
        </Button>
      </View>

      {snapshot ? (
        <View className={styles['card'] ?? ''} data-readiness={snapshot.readiness}>
          <Text className={styles['cardTitle'] ?? ''}>快照状态：{snapshot.readiness}</Text>
          <Text className={styles['meta'] ?? ''}>{snapshot.provider} · revision {snapshot.revision}</Text>
          <Text className={styles['meta'] ?? ''}>来源版本：{snapshot.provenance.sourceRevision || '未提供'}</Text>
          {snapshot.missingFields.map((field) => <Text key={field} className={styles['blocker'] ?? ''}>{field}</Text>)}
          {snapshot.blockers.map((blocker) => <Text key={blocker} className={styles['blocker'] ?? ''}>{blocker}</Text>)}
        </View>
      ) : null}

      <View className={styles['card'] ?? ''}>
        <Text className={styles['cardTitle'] ?? ''}>2. 提交模拟任务</Text>
        <View className={styles['fieldRow'] ?? ''}>
          <View className={styles['field'] ?? ''}>
            <Text className={styles['label'] ?? ''}>目标数</Text>
            <Input className={styles['input'] ?? ''} type="number" value={targets} onInput={(event) => setTargets(event.detail.value)} />
          </View>
          <View className={styles['field'] ?? ''}>
            <Text className={styles['label'] ?? ''}>迭代次数</Text>
            <Input className={styles['input'] ?? ''} type="number" value={iterations} onInput={(event) => setIterations(event.detail.value)} />
          </View>
        </View>
        <Text className={styles['hint'] ?? ''}>场景固定为 Patchwerk；结果只发布有效 DPS/HPS 与完整运行身份。</Text>
        <Button
          className={styles['primaryButton'] ?? ''}
          disabled={snapshot?.readiness !== 'READY_FOR_SIMC' || state.phase === 'submitting'}
          loading={state.phase === 'submitting'}
          onClick={() => void submit()}
        >
          创建 SimC 任务
        </Button>
      </View>

      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
          <Text>{state.errorMessage || 'SimC 暂不可用'}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={state.phase === 'signed_out' ? relogin : resolveSource}>
            {state.phase === 'signed_out' ? '重新登录' : '重试'}
          </Button>
        </View>
      ) : null}
    </View>
  )
}
