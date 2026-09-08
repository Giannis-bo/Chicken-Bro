import { useTabRootIdentity } from '../../use-tab-root-identity'
import { simcDiagnosticMessage, simcRequiredFieldLabel, simcReadinessLabel } from '../../features/simc/simc-messages'
import { simcFightStyles, simcLabel } from '../../features/simc/simc-terms'
import { isTestLoginEnabled } from '../../features/auth/test-login-mode'
import { withMiniTestLogin } from '../../features/auth/with-mini-test-login'
import Taro, { useDidShow } from '@tarojs/taro'
import { Button, Input, Picker, ScrollView, Switch, Text, Textarea, View } from '@tarojs/components'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { wowApi } from '@wow-mini/api-client'
import type { SimulationRuntimeView } from '@wow-mini/domain'
import { MiniSessionStore } from '../../features/auth/mini-session'
import { SimcModel, type SimcModelState } from '../../features/simc/simc-model'
import styles from './index.module.scss'

const fightKeys = Object.keys(simcFightStyles) as (keyof typeof simcFightStyles)[]
const sourceExamples = [
  ['Raider.IO 链接格式参考', 'https://raider.io/cn/characters/cn/silver-hand/Giannis'],
] as const
function validNumber(value: string, min: number, max: number, integer = false) {
  const number = Number(value)
  return value.trim() !== '' && Number.isFinite(number) && number >= min && number <= max && (!integer || Number.isInteger(number))
}

function SimcPage() {
  useTabRootIdentity('pages/simc/index')
  const sessions = useMemo(() => new MiniSessionStore(wowApi.webAuth), [])
  const model = useMemo(() => new SimcModel(wowApi.simc, () => sessions.createAuthContext(), { workbench: true, localizedReport: true }), [sessions])
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const [sourceUrl, setSourceUrl] = useState('')
  const [resolvedUrl, setResolvedUrl] = useState('')
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [examplesOpen, setExamplesOpen] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [fightStyle, setFightStyle] = useState<keyof typeof simcFightStyles>('Patchwerk')
  const [targets, setTargets] = useState('1')
  const [iterations, setIterations] = useState('300')
  const [maxTime, setMaxTime] = useState('300')
  const [variation, setVariation] = useState('20')
  const [targetError, setTargetError] = useState('0')
  const [raidBuffs, setRaidBuffs] = useState(true)
  const [bloodlust, setBloodlust] = useState(true)
  const [runtime, setRuntime] = useState<SimulationRuntimeView | null>(null)
  const [runtimeLoading, setRuntimeLoading] = useState(true)
  const mounted = useRef(true)
  const runtimeGeneration = useRef(0)
  const submitting = useRef(false)

  useEffect(() => {
    mounted.current = true
    const unsubscribe = model.subscribe((next) => {
      setState(next)
      if (isTestLoginEnabled() && next.phase === 'signed_out') sessions.invalidate()
    })
    return () => { mounted.current = false; runtimeGeneration.current++; unsubscribe(); model.dispose() }
  }, [model, sessions])

  const ensureSession = useCallback(async () => {
    if (!sessions.getValid()) await sessions.login()
  }, [sessions])
  const refreshRuntime = useCallback(async () => {
    const generation = ++runtimeGeneration.current
    const current = () => mounted.current && generation === runtimeGeneration.current
    setRuntimeLoading(true)
    setRuntime(null)
    try {
      await ensureSession()
      const auth = sessions.createAuthContext()
      const result = await wowApi.simc.getRuntime({ auth })
      if (current()) {
        if (result.fromFallback && (result.httpStatus === 401 || result.problemCode === 'AUTH_REQUIRED')
          && auth.kind === 'mini' && sessions.getValid()?.accessToken === auth.accessToken) sessions.invalidate()
        setRuntime(result.fromFallback ? null : result.payload)
      }
    } catch { if (current()) setRuntime(null) }
    finally { if (current()) setRuntimeLoading(false) }
  }, [ensureSession, sessions])
  useEffect(() => { if (isTestLoginEnabled() || sessions.getValid()) void refreshRuntime() }, [refreshRuntime])
  useDidShow(() => { void refreshRuntime() })

  const resolveSource = async () => {
    const source = sourceUrl.trim()
    setResolvedUrl('')
    try {
      await ensureSession()
      const snapshot = await model.resolveSource(source)
      if (snapshot && mounted.current) setResolvedUrl(source)
    } catch { await model.loadJobs() }
  }
  const submit = async () => {
    if (!canSubmit || submitting.current) return
    submitting.current = true
    try {
      const job = await model.submitJob({ fightStyle, desiredTargets: Number(targets), iterations: Number(iterations), maxTime: Number(maxTime),
        varyCombatLength: Number(variation) / 100, targetError: Number(targetError), raidBuffs, bloodlust })
      if (job && mounted.current) await Taro.navigateTo({ url: `/pages/simc/task-detail?id=${encodeURIComponent(job.id)}` })
    } catch { void Taro.showToast({ title: '页面未打开，可从任务记录查看', icon: 'none' }) }
    finally { submitting.current = false }
  }
  const relogin = async () => {
    await sessions.logout().catch(() => undefined)
    await refreshRuntime()
    if (mounted.current && sessions.getValid()) await resolveSource()
  }
  const snapshot = state.snapshot
  const busy = state.phase === 'loading' || state.phase === 'submitting'
  const currentSource = !!snapshot && resolvedUrl === sourceUrl.trim()
  const actor = currentSource ? snapshot?.character : null
  const errors = [
    !validNumber(targets, 1, 20, true) ? '目标数请填写 1–20 的整数' : '',
    !validNumber(maxTime, 30, 600, true) ? '战斗时长请填写 30–600 秒的整数' : '',
    !validNumber(iterations, 1, 10000, true) ? '迭代上限请填写 1–10000 的整数' : '',
    !validNumber(variation, 0, 50) ? '时长浮动请填写 0–50%' : '',
    !validNumber(targetError, 0, 5) ? '目标误差请填写 0–5%' : '',
  ].filter(Boolean)
  const sourceReady = currentSource && snapshot?.readiness === 'READY_FOR_SIMC'
  const canSubmit = sourceReady && errors.length === 0 && !busy && state.phase !== 'signed_out' && runtime?.status === 'available'

  return <View className={styles['page'] ?? ''} data-simc-phase={state.phase}>
    <View className={styles['header'] ?? ''}>
      <View className={styles['heading'] ?? ''}>
        <Text className={styles['title'] ?? ''}>Simc模拟</Text>
        <Text className={styles['runtime'] ?? ''} data-runtime-status={runtime?.status ?? 'unknown'}>{runtimeLoading ? 'Simc版本：读取中' : runtime?.status === 'available' ? `Simc版本：${runtime.version || '未提供'}` : 'Simc版本：暂不可用'}</Text>
      </View>
      <View className={styles['headerActions'] ?? ''}>
        <Button className={styles['secondaryButton'] ?? ''} onClick={() => void Taro.navigateTo({url: '/pages/simc/tasks'})}>任务记录</Button>
      </View>
    </View>
    <ScrollView className={styles['content'] ?? ''} scrollY>
      <View className={styles['card'] ?? ''}>
        <Text className={styles['cardTitle'] ?? ''}>1. 角色来源</Text>
        <Text className={styles['hint'] ?? ''}>仅支持 HTTPS 的 Raider.IO 角色链接，请参考示例。</Text>
        <Textarea maxlength={2048} disabled={busy} autoHeight className={styles['input'] ?? ''} placeholder="粘贴 Raider.IO 角色链接" value={sourceUrl} onInput={(e) => setSourceUrl(e.detail.value)} />
        <Button className={styles['primaryButton'] ?? ''} disabled={!sourceUrl.trim() || busy} loading={state.phase === 'loading'} onClick={() => void resolveSource()}>{state.phase === 'loading' ? '正在读取角色…' : '读取角色'}</Button>
        <Button className={styles['textButton'] ?? ''} aria-expanded={examplesOpen} onClick={() => setExamplesOpen(!examplesOpen)}>链接示例</Button>
        {examplesOpen ? sourceExamples.map(([label, url]) => <View className={styles['example'] ?? ''} key={url}>
          <Text className={styles['label'] ?? ''}>{label}</Text><Text selectable className={styles['exampleUrl'] ?? ''}>{url}</Text>
          <Button className={styles['textButton'] ?? ''} onClick={() => void Taro.setClipboardData({data: url}).catch(() => undefined)}>复制链接</Button>
        </View>) : null}
        {currentSource && snapshot ? <View className={styles['snapshot'] ?? ''} data-readiness={snapshot.readiness}>
          <Text className={styles['cardTitle'] ?? ''}>{actor?.name || '角色资料'} · {simcReadinessLabel(snapshot.readiness)}</Text>
          {actor ? <Text className={styles['hint'] ?? ''}>{simcLabel(actor.specialization)} {simcLabel(actor.className)}{actor.level == null ? '' : ` · 等级 ${actor.level}`}</Text> : null}
          {snapshot.missingFields.map(field => <Text key={field} className={styles['blocker'] ?? ''}>{simcRequiredFieldLabel(field)}</Text>)}
          {snapshot.blockers.map(blocker => <Text key={blocker} className={styles['blocker'] ?? ''}>{simcDiagnosticMessage(blocker)}</Text>)}
          <Button className={styles['textButton'] ?? ''} onClick={() => setDetailsOpen(!detailsOpen)}>{detailsOpen ? '收起来源信息' : '查看来源信息'}</Button>
          {detailsOpen ? <Text className={styles['meta'] ?? ''}>{snapshot.provider === 'raiderio' ? '角色评分网站' : '战斗日志网站'} · 资料版本 {snapshot.revision} · 来源版本 {snapshot.provenance.sourceRevision || '未提供'}</Text> : null}
        </View> : null}
      </View>
      <View className={styles['card'] ?? ''}>
        <Text className={styles['cardTitle'] ?? ''}>2. 战斗设置</Text>
        <Text className={styles['label'] ?? ''}>战斗类型</Text>
        <Picker data-field="fightStyle" mode="selector" range={Object.values(simcFightStyles)} value={fightKeys.indexOf(fightStyle)} disabled={busy} onChange={(e) => setFightStyle(fightKeys[Number(e.detail.value)] ?? 'Patchwerk')}>
          <View className={styles['select'] ?? ''}>{simcFightStyles[fightStyle]}<Text>更改 ›</Text></View>
        </Picker>
        <View className={styles['fieldRow'] ?? ''}>
          <View className={styles['field'] ?? ''}><Text className={styles['label'] ?? ''}>目标数（1–20）</Text><Input data-field="desiredTargets" className={styles['input'] ?? ''} type="number" disabled={busy} maxlength={2} value={targets} onInput={e => setTargets(e.detail.value)} /></View>
          <View className={styles['field'] ?? ''}><Text className={styles['label'] ?? ''}>时长（30–600 秒）</Text><Input data-field="maxTime" className={styles['input'] ?? ''} type="number" disabled={busy} maxlength={3} value={maxTime} onInput={e => setMaxTime(e.detail.value)} /></View>
        </View>
      </View>
      <View className={styles['card'] ?? ''}>
        <Button className={styles['disclosure'] ?? ''} aria-label="精度与增益" aria-expanded={advancedOpen} onClick={() => setAdvancedOpen(!advancedOpen)}><Text>精度与增益</Text><Text className={styles['chevron'] ?? ''} aria-hidden>{advancedOpen ? '⌃' : '⌄'}</Text></Button>
        {!advancedOpen ? <Text className={styles['hint'] ?? ''}>{iterations || '—'} 次 · 时长 ±{variation || '—'}% · 团队增益{raidBuffs ? '开' : '关'} · 嗜血{bloodlust ? '开' : '关'}</Text> : <>
          <View className={styles['fieldRow'] ?? ''}>
            <View className={styles['field'] ?? ''}><Text className={styles['label'] ?? ''}>迭代上限</Text><Input data-field="iterations" className={styles['input'] ?? ''} type="number" maxlength={5} disabled={busy} value={iterations} onInput={e => setIterations(e.detail.value)} /></View>
            <View className={styles['field'] ?? ''}><Text className={styles['label'] ?? ''}>目标误差（%）</Text><Input data-field="targetError" className={styles['input'] ?? ''} type="digit" maxlength={5} disabled={busy} value={targetError} onInput={e => setTargetError(e.detail.value)} /></View>
          </View>
          <Text className={styles['hint'] ?? ''}>迭代 1–10000 次；目标误差 0–5%，0 表示按迭代上限，大于 0 时达到精度可提前结束。</Text>
          <Text className={styles['label'] ?? ''}>时长浮动（± %）</Text><Input data-field="varyCombatLength" className={styles['input'] ?? ''} type="digit" maxlength={5} disabled={busy} value={variation} onInput={e => setVariation(e.detail.value)} />
          <Text className={styles['hint'] ?? ''}>0–50%，让每次战斗长度略有变化。</Text>
          <View className={styles['toggle'] ?? ''}><Text>团队增益</Text><Switch data-field="raidBuffs" color="#9e5145" checked={raidBuffs} disabled={busy} onChange={e => setRaidBuffs(e.detail.value)} /></View>
          <View className={styles['toggle'] ?? ''}><Text>嗜血 / 英勇</Text><Switch data-field="bloodlust" color="#9e5145" checked={bloodlust} disabled={busy} onChange={e => setBloodlust(e.detail.value)} /></View>
        </>}
      </View>
      <View className={styles['card'] ?? ''}>
        <Button className={styles['disclosure'] ?? ''} aria-label="配置摘要" aria-expanded={summaryOpen} onClick={() => setSummaryOpen(!summaryOpen)}><Text>配置摘要</Text><Text className={styles['chevron'] ?? ''} aria-hidden>{summaryOpen ? '⌃' : '⌄'}</Text></Button>
        {summaryOpen ? <>{runtime?.gameVersion ? <Text className={styles['hint'] ?? ''}>游戏版本：{runtime.gameVersion}</Text> : null}<Text className={styles['hint'] ?? ''}>{actor?.name || '等待角色资料'} · {simcFightStyles[fightStyle]} · {targets || '—'} 目标</Text>
          <Text className={styles['hint'] ?? ''}>{maxTime || '—'} 秒 · ±{variation || '—'}% · 迭代 {iterations || '—'} 次</Text>
          <Text className={styles['hint'] ?? ''}>目标误差：{targetError === '0' ? '按迭代上限' : `${targetError || '—'}%`} · 团队增益{raidBuffs ? '开启' : '关闭'} · 嗜血{bloodlust ? '开启' : '关闭'}</Text></> : null}
      </View>
      {state.phase === 'blocked' || state.phase === 'signed_out' ? <View className={styles['errorCard'] ?? ''} data-error-code={state.errorCode}>
        <Text>{state.errorCode === 'INVALID_LINK' ? '非法链接：格式不正确或来源不受支持，请参考链接示例，修改后重新读取。' : simcDiagnosticMessage(state.errorCode, state.errorMessage)}</Text>
        <Button className={styles['secondaryButton'] ?? ''} onClick={state.phase === 'signed_out' ? relogin : resolveSource}>{state.phase === 'signed_out' ? '重新登录' : '重试'}</Button>
      </View> : null}
    </ScrollView>
    <View className={styles['submitBar'] ?? ''}>
      {!runtimeLoading && runtime?.status !== 'available' ? <Button className={styles['textButton'] ?? ''} onClick={() => void refreshRuntime()}>重试引擎</Button> : null}
      <Text className={styles['submitHint'] ?? ''}>{errors[0] || (!currentSource ? (snapshot ? '链接已更改，请重新读取角色后再模拟。' : '先读取角色资料，再开始模拟。') : !sourceReady ? '请补齐角色资料' : runtime?.status !== 'available' ? '等待云端引擎可用后提交' : '云端运行，可从任务记录查看结果')}</Text>
      <Button className={styles['primaryButton'] ?? ''} disabled={!canSubmit} loading={state.phase === 'submitting'} onClick={() => void submit()}>{state.phase === 'submitting' ? '正在提交…' : '开始模拟'}</Button>
    </View>
  </View>
}
export default withMiniTestLogin(SimcPage)
