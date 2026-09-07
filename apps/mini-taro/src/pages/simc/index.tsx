import { useTabRootIdentity } from '../../use-tab-root-identity'
import { simcDiagnosticMessage, simcRequiredFieldLabel, simcReadinessLabel } from '../../features/simc/simc-messages'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import Taro, { useDidShow } from '@tarojs/taro'
import { Button, Input, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'

import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './index.module.scss'


function SimcPage() {
  useTabRootIdentity('pages/simc/index')
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(
    () => new SimcModel(wowApi.simc, () => sessions.createAuthContext()),
    [sessions],
  )
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const [sourceUrl, setSourceUrl] = useState('')
  const [resolvedUrl, setResolvedUrl] = useState('')
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [targets, setTargets] = useState('1')
  const [iterations, setIterations] = useState('300')

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

  const ensureSession = async () => {
    if (!sessions.getValid()) await sessions.login()
  }

  useEffect(() => {
    if (isTestLoginEnabled()) void ensureSession().catch(() => model.loadJobs())
  }, [model, sessions])

  useDidShow(() => {
    void ensureSession().catch(() => model.loadJobs())
  })

  const resolveSource = async () => {
    try {
      await ensureSession()
      const snapshot = await model.resolveSource(sourceUrl.trim())
      if (snapshot) setResolvedUrl(sourceUrl.trim())
    } catch {
      await model.loadJobs()
    }
  }

  const submit = async () => {
    if (!canSubmit) return
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
  const busy = state.phase === 'loading' || state.phase === 'submitting'
  const currentSource = !!snapshot && resolvedUrl === sourceUrl.trim()
  const parametersValid = /^\d+$/.test(targets) && Number(targets) >= 1 && Number(targets) <= 20
    && /^\d+$/.test(iterations) && Number(iterations) >= 1 && Number(iterations) <= 10000
  const canSubmit = currentSource && snapshot?.readiness === 'READY_FOR_SIMC' && parametersValid && !busy

  return (
    <View className={styles['page'] ?? ''} data-simc-phase={state.phase}>
      <View className={styles['header'] ?? ''}>
        <View>
          <Text className={styles['eyebrow'] ?? ''}>云端战斗模拟</Text>
          <Text className={styles['title'] ?? ''}>战斗模拟</Text>
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
        <Text className={styles['hint'] ?? ''}>粘贴 Raider.IO 角色页或 WCL 角色链接，先检查资料是否足够用于模拟。</Text>
        <Textarea
          maxlength={2048}
          disabled={busy}
          autoHeight
          className={styles['input'] ?? ''}
          placeholder="粘贴角色评分或战斗日志链接"
          value={sourceUrl}
          onInput={(event) => setSourceUrl(event.detail.value)}
        />
        <Button
          className={styles['primaryButton'] ?? ''}
          disabled={!sourceUrl.trim() || busy}
          loading={state.phase === 'loading'}
          onClick={() => void resolveSource()}
        >
          {state.phase === 'loading' ? '正在读取角色…' : '读取角色'}
        </Button>
      </View>

      {snapshot && currentSource ? (
        <View className={styles['card'] ?? ''} data-readiness={snapshot.readiness}>
          <Text className={styles['cardTitle'] ?? ''}>快照状态：{simcReadinessLabel(snapshot.readiness)}</Text>
          <Button className={styles['secondaryButton'] ?? ''} onClick={() => setDetailsOpen(!detailsOpen)}>{detailsOpen ? '收起来源信息' : '查看来源信息'}</Button>
          {detailsOpen ? <><Text className={styles['meta'] ?? ''}>{snapshot.provider === 'raiderio' ? '角色评分网站' : '战斗日志网站'} · 资料版本 {snapshot.revision}</Text>
          <Text className={styles['meta'] ?? ''}>来源版本：{snapshot.provenance.sourceRevision || '未提供'}</Text></> : null}
          {snapshot.missingFields.map((field) => <Text key={field} className={styles['blocker'] ?? ''}>{simcRequiredFieldLabel(field)}</Text>)}
          {snapshot.blockers.map((blocker) => <Text key={blocker} className={styles['blocker'] ?? ''}>{simcDiagnosticMessage(blocker)}</Text>)}
        </View>
      ) : null}

      <View className={styles['card'] ?? ''}>
        <Text className={styles['cardTitle'] ?? ''}>2. 设置模拟</Text>
        <View className={styles['fieldRow'] ?? ''}>
          <View className={styles['field'] ?? ''}>
            <Text className={styles['label'] ?? ''}>目标数</Text>
            <Input className={styles['input'] ?? ''} type="number" disabled={busy} maxlength={2} value={targets} onInput={(event) => setTargets(event.detail.value)} />
          </View>
          <View className={styles['field'] ?? ''}>
            <Text className={styles['label'] ?? ''}>迭代次数</Text>
            <Input className={styles['input'] ?? ''} type="number" disabled={busy} maxlength={5} value={iterations} onInput={(event) => setIterations(event.detail.value)} />
          </View>
        </View>
        <Text className={styles['hint'] ?? ''}>站桩模拟 · 目标数 1–20 · 迭代 1–10000 次。次数越多，用时通常越长。</Text>
        <Button
          className={styles['primaryButton'] ?? ''}
          disabled={!canSubmit}
          loading={state.phase === 'submitting'}
          onClick={() => void submit()}
        >
          {state.phase === 'submitting' ? '正在提交…' : '开始模拟'}
        </Button>
      </View>

      {!currentSource ? <Text className={styles['hint'] ?? ''}>{snapshot ? '链接已更改，请重新读取角色后再模拟。' : '先读取角色资料，再开始模拟。'}</Text> : null}
      {!parametersValid ? <Text className={styles['blocker'] ?? ''}>请填写范围内的整数：目标数 1–20，迭代次数 1–10000。</Text> : null}

      {state.phase === 'blocked' || state.phase === 'signed_out' ? (
        <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
          <Text>{simcDiagnosticMessage(state.errorCode, state.errorMessage)}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={state.phase === 'signed_out' ? relogin : resolveSource}>
            {state.phase === 'signed_out' ? '重新登录' : '重试'}
          </Button>
        </View>
      ) : null}
    </View>
  )
}

export default withMiniTestLogin(SimcPage)
