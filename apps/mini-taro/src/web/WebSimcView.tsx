import { simcDiagnosticMessage, simcRequiredFieldLabel, simcReadinessLabel } from '../features/simc/simc-messages'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'
import type { SimulationJobDetail, SimulationJobStatus, SimulationRuntimeView } from '@wow-mini/domain'

import { SimcModel, shouldPollSimulationJob, type SimcModelState } from '../features/simc/simc-model'
import WebSimcReport from './WebSimcReport'
import { simcDate, simcFightStyles, simcLabel, simcMetricName, simcNumber, simcStatuses } from './simc-presentation'
import styles from './WebSimc.module.scss'

type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type WorkbenchPage = 'new' | 'tasks' | 'report'

export interface WebSimcViewProps { auth: WebClientAuth }

function validNumber(value: string, minimum: number, maximum: number, integer = false): boolean {
  const number = Number(value)
  return value.trim() !== '' && Number.isFinite(number) && number >= minimum && number <= maximum && (!integer || Number.isInteger(number))
}

export default function WebSimcView({ auth }: WebSimcViewProps) {
  const model = useMemo(() => new SimcModel(wowApi.simc, () => auth, { workbench: true }), [auth])
  const [state, setState] = useState<SimcModelState>(() => model.get())
  const [page, setPage] = useState<WorkbenchPage>('new')
  const [filter, setFilter] = useState<SimulationJobStatus | 'all'>('all')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [opening, setOpening] = useState(false)
  const [sourceUrl, setSourceUrl] = useState('')
  const [resolvedSource, setResolvedSource] = useState('')
  const [resolving, setResolving] = useState(false)
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
  const disposedRef = useRef(false)
  const navigationRef = useRef(0)
  const runtimeGenerationRef = useRef(0)

  const refreshRuntime = useCallback(async () => {
    const generation = ++runtimeGenerationRef.current
    const current = () => !disposedRef.current && generation === runtimeGenerationRef.current
    setRuntime(null)
    setRuntimeLoading(true)
    try {
      const result = await wowApi.simc.getRuntime({ auth })
      if (current()) setRuntime(result.fromFallback ? null : result.payload)
    } catch {
      if (current()) setRuntime(null)
    } finally {
      if (current()) setRuntimeLoading(false)
    }
  }, [auth])

  useEffect(() => {
    disposedRef.current = false
    const unsubscribe = model.subscribe(setState)
    void model.loadJobs()
    void refreshRuntime()
    return () => {
      disposedRef.current = true
      navigationRef.current += 1
      runtimeGenerationRef.current += 1
      unsubscribe()
      model.dispose()
    }
  }, [model, refreshRuntime])

  const navigate = (next: WorkbenchPage) => {
    navigationRef.current += 1
    setPage(next)
    setOpening(false)
    if (next === 'tasks') void model.loadJobs()
    if (next === 'new') void refreshRuntime()
  }
  const poll = async (job: SimulationJobDetail, generation: number) => {
    if (!shouldPollSimulationJob(job)) return
    const completed = await model.pollJob(job.id, {
      cancelled: () => disposedRef.current || navigationRef.current !== generation,
    })
    if (!disposedRef.current && navigationRef.current === generation && completed && !shouldPollSimulationJob(completed)) {
      await model.loadJobs()
    }
  }
  const submit = async () => {
    if (!canSubmit) return
    const generation = navigationRef.current
    const job = await model.submitJob({
      fightStyle, desiredTargets: Number(targets), iterations: Number(iterations), maxTime: Number(maxTime),
      varyCombatLength: Number(variation) / 100, targetError: Number(targetError), raidBuffs, bloodlust,
    })
    if (job && !disposedRef.current && generation === navigationRef.current) {
      setSelectedJobId(job.id)
      setPage('report')
      await poll(job, generation)
    }
  }
  const openJob = async (jobId: string) => {
    const generation = ++navigationRef.current
    setSelectedJobId(jobId)
    setPage('report')
    setOpening(true)
    const job = await model.loadJob(jobId)
    if (disposedRef.current || generation !== navigationRef.current) return
    setOpening(false)
    if (job) await poll(job, generation)
  }
  const resolve = async () => {
    setResolving(true)
    setResolvedSource('')
    const source = sourceUrl.trim()
    const snapshot = await model.resolveSource(source)
    if (!disposedRef.current) {
      if (snapshot) setResolvedSource(source)
      setResolving(false)
    }
  }

  const snapshot = state.snapshot
  const snapshotCurrent = snapshot && sourceUrl.trim() === resolvedSource
  const actor = snapshotCurrent ? snapshot.character : null
  const scenarioValid = validNumber(targets, 1, 20, true) && validNumber(iterations, 1, 10000, true)
    && validNumber(maxTime, 30, 600, true) && validNumber(variation, 0, 50) && validNumber(targetError, 0, 5)
  const sourceReady = snapshotCurrent && snapshot.readiness === 'READY_FOR_SIMC'
  const canSubmit = Boolean(sourceReady && scenarioValid && !resolving && state.phase !== 'submitting' && state.phase !== 'signed_out' && runtime?.status === 'available')
  const filteredJobs = state.jobs.filter((job) => filter === 'all' || job.status === filter)
  const activeJob = selectedJobId === state.activeJob?.id ? state.activeJob : null

  return <div className={styles['workbench']} data-simc-phase={state.phase} data-simc-page={page}>
    <header className={styles['header']}>
      <div><p className={styles['eyebrow']}>云端战斗模拟</p><h1>模拟工作台</h1></div>
      <div className={styles['engine']} data-runtime-status={runtime?.status ?? 'unknown'}>
        <span className={styles['engineDot']} aria-hidden="true" />
        <div><strong>{runtimeLoading ? '正在读取云端引擎…' : runtime?.status === 'available' && runtime.version ? `模拟引擎 ${runtime.version}` : runtime?.status === 'unavailable' ? '引擎暂不可用' : '引擎版本暂不可用'}</strong>
          <small>当前云端引擎{runtime?.gameVersion ? ` · 游戏 ${runtime.gameVersion}` : ''}</small></div>
        {!runtimeLoading && runtime?.status !== 'available' ? <button data-simc-button="" className={styles['textButton']} onClick={() => void refreshRuntime()}>重试引擎</button> : null}
      </div>
    </header>
    <nav className={styles['navigation']} aria-label="模拟工作台">
      <button data-simc-button="" aria-current={page === 'new' ? 'page' : undefined} onClick={() => navigate('new')}>新建模拟</button>
      <button data-simc-button="" aria-current={page !== 'new' ? 'page' : undefined} onClick={() => navigate('tasks')}>模拟任务</button>
    </nav>

    {state.phase === 'blocked' || state.phase === 'signed_out' ? <div className={styles['error']} role="alert" data-error-code={state.errorCode}>
      <span>{state.phase === 'signed_out' ? '网页登录已失效，请重新扫码登录' : simcDiagnosticMessage(state.errorCode, state.errorMessage)}</span>
      {state.retryable && state.phase !== 'signed_out' ? <button data-simc-button="" className={styles['textButton']} onClick={() => {
        if (page === 'report' && selectedJobId) void openJob(selectedJobId)
        else if (page === 'tasks') void model.loadJobs()
        else if (sourceUrl.trim()) void resolve()
      }}>重试</button> : null}
    </div> : null}

    {page === 'new' ? <>
      <div className={styles['pageIntro']}><h2>开始一次模拟</h2><p>读取角色，设置战斗条件，查看云端模拟结果。</p></div>
      <div className={styles['setupGrid']}>
        <div className={styles['configStack']}>
          <section className={styles['card']}>
            <div className={styles['sectionHeading']}><h3><span className={styles['step']}>01</span>角色来源</h3><span>从链接读取角色</span></div>
            <label data-simc-label="" className={styles['field']}><span>角色评分或战斗日志链接</span>
              <div className={styles['sourceRow']}><input data-simc-input="" name="sourceUrl" type="url" value={sourceUrl} placeholder="粘贴角色或战斗报告的安全链接" onChange={(event) => setSourceUrl(event.target.value)} />
                <button data-simc-button="" className={styles['secondaryButton']} disabled={!sourceUrl.trim() || resolving || state.phase === 'submitting'} onClick={() => void resolve()}>{resolving ? '读取中…' : '读取角色'}</button></div>
            </label>
            <div className={styles['sourceExamples']} aria-label="合法链接格式示例">
              <p className={styles['hint']}>合法链接示例 · Giannis－白银之手</p>
              <div><span className={styles['exampleLabel']}>角色评分（Raider.IO）</span>
                <a className={styles['exampleLink']} href="https://raider.io/cn/characters/cn/silver-hand/Giannis" target="_blank" rel="noreferrer">https://raider.io/cn/characters/cn/silver-hand/Giannis</a></div>
              <div><span className={styles['exampleLabel']}>战斗日志（WCL，已指定战斗和角色）</span>
                <a className={styles['exampleLink']} href="https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4" target="_blank" rel="noreferrer">https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&amp;source=4</a></div>
            </div>
            {snapshotCurrent ? <div className={styles['snapshot']} data-readiness={snapshot.readiness}>
              <strong>{sourceReady ? '角色已就绪' : simcReadinessLabel(snapshot.readiness)}{actor ? ` · ${actor.name}` : ''}</strong>
              {actor ? <p>{simcLabel(actor.specialization)} {simcLabel(actor.className)}{actor.level == null ? '' : ` · 等级 ${actor.level}`}</p> : null}
              {!sourceReady ? <p>补齐以下资料后才能模拟；不会使用猜测数据。</p> : null}
              {snapshot.missingFields.length ? <p>缺少：{snapshot.missingFields.map(simcRequiredFieldLabel).join('、')}</p> : null}
              {snapshot.blockers.map((blocker) => <p key={blocker}>{simcDiagnosticMessage(blocker)}</p>)}
            </div> : null}
          </section>
          <section className={styles['card']}>
            <div className={styles['sectionHeading']}><h3><span className={styles['step']}>02</span>战斗设置</h3></div>
            <div className={styles['fieldGrid']}>
              <label data-simc-label="" className={styles['field']}><span>战斗类型</span><select name="fightStyle" value={fightStyle} onChange={(event) => setFightStyle(event.target.value as keyof typeof simcFightStyles)}>
                {Object.entries(simcFightStyles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select></label>
              <label data-simc-label="" className={styles['field']}><span>目标数</span><input data-simc-input="" name="desiredTargets" type="number" min="1" max="20" step="1" value={targets} onChange={(event) => setTargets(event.target.value)} /><small>1–20 个目标</small></label>
              <label data-simc-label="" className={styles['field']}><span>战斗时长（秒）</span><input data-simc-input="" name="maxTime" type="number" min="30" max="600" value={maxTime} onChange={(event) => setMaxTime(event.target.value)} /><small>30–600 秒</small></label>
              <label data-simc-label="" className={styles['field']}><span>时长浮动（± %）</span><input data-simc-input="" name="varyCombatLength" type="number" min="0" max="50" value={variation} onChange={(event) => setVariation(event.target.value)} /><small>0–50%，让每次战斗长度略有变化</small></label>
            </div>
          </section>
          <section className={styles['card']}>
            <div className={styles['sectionHeading']}><h3><span className={styles['step']}>03</span>精度与增益</h3></div>
            <div className={styles['fieldGrid']}>
              <label data-simc-label="" className={styles['field']}><span>迭代上限</span><input data-simc-input="" name="iterations" type="number" min="1" max="10000" step="1" value={iterations} onChange={(event) => setIterations(event.target.value)} /><small>1–10,000 次，增加次数可降低随机误差</small></label>
              <label data-simc-label="" className={styles['field']}><span>目标误差（%）</span><input data-simc-input="" name="targetError" type="number" min="0" max="5" step="0.1" value={targetError} onChange={(event) => setTargetError(event.target.value)} /><small>0 表示按迭代上限；大于 0 时达到精度可提前结束</small></label>
            </div>
            <div className={styles['toggles']}>
              <label data-simc-label=""><div><strong>团队增益</strong><small>启用标准团队增益</small></div><input data-simc-input="" name="raidBuffs" type="checkbox" checked={raidBuffs} onChange={(event) => setRaidBuffs(event.target.checked)} /></label>
              <label data-simc-label=""><div><strong>嗜血 / 英勇</strong><small>启用战斗中的急速增益</small></div><input data-simc-input="" name="bloodlust" type="checkbox" checked={bloodlust} onChange={(event) => setBloodlust(event.target.checked)} /></label>
            </div>
          </section>
        </div>
        <aside className={`${styles['card']} ${styles['summary']}`} aria-label="本次模拟摘要">
          <p className={styles['eyebrow']}>配置摘要</p><h3>本次模拟</h3>
          <div className={styles['characterSummary']}><span className={styles['characterMark']} aria-hidden="true">{actor?.name.slice(0, 1) || '◇'}</span><div><strong>{actor?.name || '等待角色资料'}</strong><small>{actor ? `${simcLabel(actor.specialization)} ${simcLabel(actor.className)}` : '先读取角色来源'}</small></div></div>
          <dl className={styles['summaryList']}>
            <div><dt>战斗类型</dt><dd>{simcFightStyles[fightStyle]}</dd></div><div><dt>目标数量</dt><dd>{targets || '—'} 个</dd></div>
            <div><dt>战斗时长</dt><dd>{maxTime || '—'} 秒 · ± {variation || '—'}%</dd></div><div><dt>迭代上限</dt><dd>{iterations || '—'} 次</dd></div>
            <div><dt>目标误差</dt><dd>{targetError === '0' ? '按迭代上限' : `${targetError || '—'}%`}</dd></div>
            <div><dt>团队增益</dt><dd>{raidBuffs ? '开启' : '关闭'}</dd></div><div><dt>嗜血 / 英勇</dt><dd>{bloodlust ? '开启' : '关闭'}</dd></div>
          </dl>
          <button data-simc-button="" className={styles['primaryButton']} disabled={!canSubmit} onClick={() => void submit()}>{state.phase === 'submitting' ? '正在提交…' : '开始模拟'}</button>
          <p className={styles['submitHint']}>{!sourceReady ? '读取完整角色资料后即可提交' : !scenarioValid ? '请检查参数范围，所有数值均需填写' : runtime?.status !== 'available' ? '等待云端引擎可用后提交' : '任务在云端运行，可在模拟任务中继续查看'}</p>
        </aside>
      </div>
    </> : null}

    {page === 'tasks' ? <section>
      <div className={styles['pageIntro']}><div><h2>模拟任务</h2><p>查看本账号在网页与小程序提交的模拟。</p></div><button data-simc-button="" className={styles['secondaryButton']} disabled={state.phase === 'loading'} onClick={() => void model.loadJobs()}>刷新任务</button></div>
      <div className={styles['taskToolbar']}><div className={styles['filters']} aria-label="任务状态筛选">
        {(['all', 'queued', 'running', 'succeeded', 'failed', 'cancelled'] as const).map((status) => <button data-simc-button="" key={status} aria-pressed={filter === status} onClick={() => setFilter(status)}>{status === 'all' ? '全部' : simcStatuses[status]}</button>)}
      </div><span className={styles['muted']}>已加载 {state.jobs.length} 项</span></div>
      <div className={styles['taskList']}>
        {filteredJobs.map((job) => <button data-simc-button="" key={job.id} className={styles['taskRow']} data-job-id={job.id} onClick={() => void openJob(job.id)}>
          <span className={styles['taskCharacter']}><strong>{job.character?.name || '角色信息未记录'}</strong><small>{job.character ? `${simcLabel(job.character.specialization)} ${simcLabel(job.character.className)}` : `任务 ${job.id.slice(0, 8)}`}</small></span>
          <span className={styles['taskScenario']}>{job.scenario ? `${simcFightStyles[job.scenario.fightStyle as keyof typeof simcFightStyles] ?? '未记录战斗类型'} · ${job.scenario.desiredTargets} 目标` : '配置未记录'}<small>{simcDate(job.createdAt)}</small></span>
          <span className={styles['taskMetric']}>{job.metric ? <><strong>{simcNumber(job.metric.value)}</strong><small>{simcMetricName(job.metric.name)}</small></> : <small>{job.status === 'queued' || job.status === 'running' ? '等待结果' : '无结果'}</small>}</span>
          <span className={styles['status']} data-status={job.status}>{simcStatuses[job.status]}</span><span className={styles['rowArrow']} aria-hidden="true">→</span>
        </button>)}
      </div>
      {!filteredJobs.length && state.phase !== 'blocked' && state.phase !== 'signed_out' ? <div className={styles['empty']} role="status"><h3>{state.phase === 'loading' ? '正在读取任务…' : filter === 'all' ? '还没有模拟任务' : '暂无此状态的任务'}</h3><p>{filter === 'all' ? '读取角色并开始模拟，你的结果会保存在这里。' : '切换其他状态查看，或刷新任务列表。'}</p></div> : null}
      {state.nextCursor ? <button data-simc-button="" className={styles['loadMore']} disabled={state.phase === 'loading'} onClick={() => void model.loadJobs(state.nextCursor ?? undefined)}>{state.phase === 'loading' ? '正在加载…' : '加载更多任务'}</button> : null}
    </section> : null}
    {page === 'report' ? activeJob && !opening ? <WebSimcReport job={activeJob} onBack={() => navigate('tasks')} onRefresh={() => void openJob(activeJob.id)} refreshing={opening} /> : <div className={styles['empty']}><button data-simc-button="" className={styles['backButton']} onClick={() => navigate('tasks')}>返回模拟任务</button><p role="status">{opening ? '正在读取模拟报告…' : '暂时无法读取报告，请重试。'}</p></div> : null}
  </div>
}
