import { Button, Input, ScrollView, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useRef, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'
import type { SimulationJobDetail } from '@wow-mini/domain'

import { SimcModel, shouldPollSimulationJob, type SimcModelState } from '../features/simc/simc-model'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>

export interface WebSimcViewProps {
  auth: WebClientAuth
}

function validInteger(value: string, minimum: number, maximum: number): boolean {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= minimum && parsed <= maximum
}

export default function WebSimcView({ auth }: WebSimcViewProps) {
  const model = useMemo(() => new SimcModel(wowApi.simc, () => auth), [auth])
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const [sourceUrl, setSourceUrl] = useState('')
  const [targets, setTargets] = useState('1')
  const [iterations, setIterations] = useState('300')
  const disposedRef = useRef(false)

  useEffect(() => {
    disposedRef.current = false
    const unsubscribe = model.subscribe(setState)
    void model.loadJobs()
    return () => {
      disposedRef.current = true
      unsubscribe()
    }
  }, [model])

  const poll = async (job: SimulationJobDetail) => {
    if (!shouldPollSimulationJob(job)) return
    const completed = await model.pollJob(job.id, { cancelled: () => disposedRef.current })
    if (!disposedRef.current && completed && !shouldPollSimulationJob(completed)) {
      await model.loadJobs()
    }
  }

  const submit = async () => {
    const job = await model.submitJob({
      fightStyle: 'Patchwerk',
      desiredTargets: Number(targets),
      iterations: Number(iterations),
    })
    if (job) await poll(job)
  }

  const openJob = async (jobId: string) => {
    const job = await model.loadJob(jobId)
    if (job) await poll(job)
  }

  const snapshot = state.snapshot
  const activeJob = state.activeJob
  const scenarioValid = validInteger(targets, 1, 20) && validInteger(iterations, 1, 10000)

  return (
    <View className={styles['businessView'] ?? ''} data-simc-phase={state.phase}>
      <View className={styles['viewHeader'] ?? ''}>
        <View>
          <Text className={styles['viewEyebrow'] ?? ''}>SIMULATIONCRAFT</Text>
          <Text className={styles['viewTitle'] ?? ''}>SimC 模拟</Text>
        </View>
        <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.loadJobs()}>
          刷新任务
        </Button>
      </View>

      <View className={styles['simcGrid'] ?? ''}>
        <View className={styles['simcControls'] ?? ''}>
          <View className={styles['workspaceCard'] ?? ''}>
            <Text className={styles['sectionTitle'] ?? ''}>1. 读取角色来源</Text>
            <Text className={styles['listMeta'] ?? ''}>仅接受 Raider.IO 或 Warcraft Logs 的 HTTPS 角色链接。</Text>
            <Input
              className={styles['webInput'] ?? ''}
              placeholder="粘贴 Raider.IO / WCL 链接"
              value={sourceUrl}
              onInput={(event) => setSourceUrl(event.detail.value)}
            />
            <Button
              className={styles['primaryButton'] ?? ''}
              disabled={!sourceUrl.trim() || state.phase === 'loading'}
              loading={state.phase === 'loading'}
              onClick={() => void model.resolveSource(sourceUrl)}
            >
              检查角色快照
            </Button>
          </View>

          {snapshot ? (
            <View className={styles['snapshotBox'] ?? ''} data-readiness={snapshot.readiness}>
              <Text className={styles['sectionTitle'] ?? ''}>快照状态：{snapshot.readiness}</Text>
              <Text className={styles['listMeta'] ?? ''}>{snapshot.provider} · revision {snapshot.revision}</Text>
              <Text className={styles['listMeta'] ?? ''}>来源版本：{snapshot.provenance.sourceRevision || '未提供'}</Text>
              {snapshot.missingFields.map((field) => <Text key={field} className={styles['errorText'] ?? ''}>{field}</Text>)}
              {snapshot.blockers.map((blocker) => <Text key={blocker} className={styles['errorText'] ?? ''}>{blocker}</Text>)}
            </View>
          ) : null}

          <View className={styles['workspaceCard'] ?? ''}>
            <Text className={styles['sectionTitle'] ?? ''}>2. 提交模拟任务</Text>
            <View className={styles['controlRow'] ?? ''}>
              <View>
                <Text className={styles['listMeta'] ?? ''}>目标数</Text>
                <Input className={styles['webInput'] ?? ''} type="number" value={targets} onInput={(event) => setTargets(event.detail.value)} />
              </View>
              <View>
                <Text className={styles['listMeta'] ?? ''}>迭代次数</Text>
                <Input className={styles['webInput'] ?? ''} type="number" value={iterations} onInput={(event) => setIterations(event.detail.value)} />
              </View>
            </View>
            <Text className={styles['listMeta'] ?? ''}>场景固定为 Patchwerk；只展示已发布的语义结果与完整运行身份。</Text>
            <Button
              className={styles['primaryButton'] ?? ''}
              disabled={snapshot?.readiness !== 'READY_FOR_SIMC' || !scenarioValid || state.phase === 'submitting'}
              loading={state.phase === 'submitting'}
              onClick={() => void submit()}
            >
              创建 SimC 任务
            </Button>
          </View>

          {state.phase === 'blocked' || state.phase === 'signed_out' ? (
            <View className={styles['inlineError'] ?? ''} data-error-code={state.errorCode}>
              <Text>{state.phase === 'signed_out' ? 'Web 登录已失效，请重新扫码登录' : state.errorMessage}</Text>
            </View>
          ) : null}
        </View>

        <View className={styles['resultPane'] ?? ''}>
          <View className={styles['workspaceCard'] ?? ''}>
            <Text className={styles['sectionTitle'] ?? ''}>任务历史</Text>
            <ScrollView className={styles['jobHistory'] ?? ''} scrollY>
              {state.jobs.map((job) => (
                <Button
                  key={job.id}
                  className={styles['jobButton'] ?? ''}
                  data-active={activeJob?.id === job.id ? 'true' : 'false'}
                  onClick={() => void openJob(job.id)}
                >
                  <Text>{job.status}</Text>
                  <Text className={styles['listMeta'] ?? ''}>{job.id}</Text>
                  <Text className={styles['listMeta'] ?? ''}>{job.createdAt}</Text>
                </Button>
              ))}
              {state.nextCursor ? (
                <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={() => void model.loadJobs(state.nextCursor ?? undefined)}>
                  加载更多
                </Button>
              ) : null}
              {!state.jobs.length && state.phase === 'ready' ? (
                <Text className={styles['emptyCopy'] ?? ''}>还没有服务端模拟任务。</Text>
              ) : null}
            </ScrollView>
          </View>

          {activeJob ? (
            <View className={styles['workspaceCard'] ?? ''} data-job-status={activeJob.status}>
              <Text className={styles['sectionTitle'] ?? ''}>任务 {activeJob.status}</Text>
              <Text className={styles['listMeta'] ?? ''}>ID：{activeJob.id}</Text>
              <Text className={styles['listMeta'] ?? ''}>编译器：{activeJob.compilerRevision}</Text>
              <Text className={styles['listMeta'] ?? ''}>运行时：{activeJob.runtimeRevision}</Text>
              {activeJob.errorCode ? <Text className={styles['errorText'] ?? ''}>{activeJob.errorCode}</Text> : null}
              {activeJob.result ? (
                <View className={styles['semanticResult'] ?? ''} data-result-id={activeJob.result.id}>
                  <Text className={styles['metric'] ?? ''}>
                    {activeJob.result.metricValue.toLocaleString()} {activeJob.result.metricName.toUpperCase()}
                  </Text>
                  <Text className={styles['listMeta'] ?? ''}>profile {activeJob.result.profileSha256}</Text>
                  <Text className={styles['listMeta'] ?? ''}>scenario {activeJob.result.provenance.scenarioHash}</Text>
                </View>
              ) : null}
            </View>
          ) : null}
        </View>
      </View>
    </View>
  )
}
