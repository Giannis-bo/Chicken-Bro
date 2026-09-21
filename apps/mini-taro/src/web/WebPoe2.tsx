import {useEffect, useRef, useState} from 'react'
import {wowApi, type ClientAuthContext, type ApiResult} from '@wow-mini/api-client'
import type {Poe2Build, Poe2Changes, Poe2Comparison, Poe2Job} from '@wow-mini/domain'
import {poe2Term, poe2GemInput, poe2Slots, poe2Config} from '@wow-mini/domain'
import styles from './WebPoe2.module.scss'
import Poe2PassiveTree from './Poe2PassiveTree'
import Poe2SkillCards from './Poe2SkillCards'

type Auth = Extract<ClientAuthContext, {kind: 'web'}>
const labels: Record<string, string> = {Str: '力量', Dex: '敏捷', Int: '智慧', Spirit: '精魂', Life: '生命', Mana: '魔力', EnergyShield: '能量护盾', CombinedDPS: '综合 DPS', TotalDPS: '命中 DPS', TotalEHP: '有效生命', Armour: '护甲', Evasion: '闪避', FireResist: '火焰抗性', ColdResist: '冰冷抗性', LightningResist: '闪电抗性', ChaosResist: '混沌抗性', LifeRegen: '生命回复', PhysicalMaximumHitTaken: '物理最大承伤'}
const stateLabels = {queued: '排队中', running: '计算中', succeeded: '已完成', failed: '失败'}
const errors: Record<string, string> = {
  POE2_ENGINE_BUSY: '计算资源正在使用，请稍后重试。', POE2_ENGINE_TIMEOUT: '此构筑计算超时，请精简方案后重试。',
  POE2_ENGINE_UNAVAILABLE: '计算引擎暂不可用，请稍后重试。', POE2_BUILD_FORMAT_INVALID: '这里只接受 PoB 2 字符串，请重新复制完整导入码。',
  POE2_BUILD_INPUT_INVALID: '分享码无效，请检查是否复制完整。', POE2_ITEM_UNRECOGNIZED: '引擎未识别这件装备，请检查复制的装备文本。',
  POE2_GEM_UNRECOGNIZED: '引擎未识别技能，请核对名称、阶级与版本；未收录的国服名称需先核实。', POE2_PASSIVE_POINTS_EXCEEDED: '分配的天赋点超过角色等级预算。',
  POE2_NODE_UNREACHABLE: '此天赋节点无法从当前树连接，请检查节点 ID。', AUTH_REQUIRED: '登录已失效，请重新登录。',
}
const errorMessage = (code: string) => errors[code] ? `${errors[code]}（${code}）` : code
function describeChanges(changes: Poe2Changes): string {
  const parts: string[] = []
  if (changes.items) parts.push(...changes.items.map(item => `替换 ${poe2Slots[item.slot] ?? `${item.slot}（槽位待核对）`}`))
  if (changes.skillGroups) parts.push(...changes.skillGroups.map(group => `技能组 ${group.index}：${group.gems.map(gem => `${poe2Term(gem.name, 'gem')} ${gem.level}级`).join(' / ')}`))
  if (changes.mainSocketGroup) parts.push(`主技能组 ${changes.mainSocketGroup}`)
  if (changes.level) parts.push(`角色 ${changes.level} 级`)
  if (changes.config) parts.push(`配置：${poe2Config(changes.config).join('；') || '其他配置（原始字段见详情）'}`)
  if (changes.allocateNodes) parts.push(`分配节点 ${changes.allocateNodes.join(', ')}`)
  if (changes.deallocateNodes) parts.push(`取消节点 ${changes.deallocateNodes.join(', ')}`)
  return parts.join('；') || '原始构筑与配置'
}
function value<T>(response: ApiResult<T>): NonNullable<T> {
  if (response.fromFallback || response.payload == null) throw new Error(response.problemCode || '请求失败，请重试')
  return response.payload
}
const number = (n: number) => n.toLocaleString('zh-CN', {maximumFractionDigits: 2})

export default function WebPoe2({auth}: {auth: Auth}) {
  const [builds, setBuilds] = useState<Poe2Build[]>([])
  const [selected, setSelected] = useState('')
  const [deleteTarget, setDeleteTarget] = useState('')
  const [copyStatus, setCopyStatus] = useState('')
  const [jobs, setJobs] = useState<Poe2Job[]>([])
  const [source, setSource] = useState('')
  const [title, setTitle] = useState('')
  const [overviewLoading, setOverviewLoading] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [exportCode, setExportCode] = useState('')
  const [comparison, setComparison] = useState<Poe2Comparison | null>(null)
  const [step, setStep] = useState(1)
  const [compareRetry, setCompareRetry] = useState(0)
  const [comparing, setComparing] = useState(false)
  const [editKind, setEditKind] = useState('item')
  const [slot, setSlot] = useState('Ring 1')
  const [itemText, setItemText] = useState('')
  const [level, setLevel] = useState('90')
  const [nodes, setNodes] = useState('')
  const [nodeAction, setNodeAction] = useState('allocateNodes')
  const [group, setGroup] = useState('1')
  const [gems, setGems] = useState('')
  const [boss, setBoss] = useState('Pinnacle')
  const generation = useRef(0)
  const selectionEpoch = useRef(0)
  const inFlight = useRef(false)
  const pendingCalculation = useRef<{signature: string; key: string} | null>(null)
  const activeBuild = builds.find(build => build.id === selected)
  const currentJobs = jobs.filter(job => job.buildId === selected)
  const baseline = currentJobs.find(job => Object.keys(job.changes).length === 0)
  const resultJob = baseline
  const candidate = currentJobs.find(job => Object.keys(job.changes).length > 0)
  const baselineId = baseline?.status === 'succeeded' ? baseline.id : ''
  const candidateId = candidate?.status === 'succeeded' ? candidate.id : ''
  const pending = jobs.some(job => job.status === 'queued' || job.status === 'running')
  const calculating = busy || pending || overviewLoading

  useEffect(() => {
    const current = ++generation.current
    const selection = ++selectionEpoch.current
    inFlight.current = false; pendingCalculation.current = null
    setSource(''); setTitle(''); setItemText(''); setGems(''); setNodes(''); setError(''); setBusy(false)
    setBuilds([]); setSelected(''); setDeleteTarget(''); setJobs([]); setStep(1); setComparison(null); setExportCode('')
    void wowApi.poe2.listBuilds(auth).then(response => {
      if (generation.current !== current) return
      const rows = value(response).items
      if (selectionEpoch.current !== selection) {
        setBuilds(existing => [...existing, ...rows.filter(row => !existing.some(build => build.id === row.id))])
        return
      }
      setBuilds(rows); setSelected(rows[0]?.id ?? '')
    }).catch(e => {if (generation.current === current && selectionEpoch.current === selection) setError(String(e.message))})
    return () => {generation.current++}
  }, [auth])
  useEffect(() => {
    let alive = true
    setCopyStatus('')
    setJobs(current => current.filter(job => job.buildId === selected)); setComparison(null); setExportCode('')
    setOverviewLoading(Boolean(selected))
    if (selected) void wowApi.poe2.listJobs(selected, auth).then(async response => {
      const rows = value(response).items
      if (!alive) return
      if (!rows.some(job => Object.keys(job.changes).length === 0)) {
        const job = value(await wowApi.poe2.calculate({buildId: selected, changes: {}, idempotencyKey: `overview:${selected}`}, auth))
        if (!alive) return
        rows.unshift(job)
      }
      setJobs(rows)
    })
      .catch(e => {if (alive) setError(String(e.message))})
      .finally(() => {if (alive) setOverviewLoading(false)})
    return () => {alive = false}
  }, [selected, auth])
  useEffect(() => {
    let alive = true
    setComparison(null)
    setComparing(Boolean(baselineId && candidateId))
    if (baselineId && candidateId) void wowApi.poe2.compare([baselineId, candidateId], auth).then(response => {
      if (alive) setComparison(value(response))
    }).catch(e => {if (alive) setError(String(e.message))})
      .finally(() => {if (alive) setComparing(false)})
    return () => {alive = false}
  }, [baselineId, candidateId, auth, compareRetry])
  useEffect(() => {
    const pending = jobs.filter(job => job.status === 'queued' || job.status === 'running')
    if (!pending.length) return
    let alive = true
    const timer = window.setTimeout(() => {
      void Promise.all(pending.map(job => wowApi.poe2.getJob(job.id, auth).then(value))).then(updates => {
        if (alive) setJobs(current => current.map(job => updates.find(update => update.id === job.id) ?? job))
      }).catch(e => {if (alive) setError(String(e.message))})
    }, 2000)
    return () => {alive = false; window.clearTimeout(timer)}
  }, [jobs, auth])

  const perform = async (operation: (active: () => boolean) => Promise<void>) => {
    if (inFlight.current) return
    inFlight.current = true
    const current = generation.current
    const active = () => generation.current === current
    setBusy(true); setError('')
    try {await operation(active)} catch (e) {if (active()) setError(e instanceof Error ? e.message : '请求失败，请重试')}
    finally {if (active()) {inFlight.current = false; setBusy(false)}}
  }
  const importBuild = () => perform(async active => {
    const code = source.trim()
    if (!code || !/^[A-Za-z0-9+/_-]+={0,2}$/u.test(code)) throw new Error('这里只接受 PoB 2 字符串。请在 poe.ninja 的 POE2 角色页找到 IMPORT CODE FOR PATH OF BUILDING，点击复制后粘贴完整导入码。')
    const build = value(await wowApi.poe2.importBuild({source: code, title: title.trim() || '我的 POE2 构筑', league: ''}, auth))
    if (!active()) return
    selectionEpoch.current++
    setBuilds(current => [build, ...current.filter(item => item.id !== build.id)])
    setSelected(build.id); setSource(''); setStep(1)
  })
  const deleteBuild = (buildId: string) => perform(async active => {
    value(await wowApi.poe2.deleteBuild(buildId, auth))
    if (!active()) return
    selectionEpoch.current++
    setBuilds(current => current.filter(build => build.id !== buildId))
    setDeleteTarget('')
    if (selected === buildId) {
      setSelected(builds.find(build => build.id !== buildId)?.id ?? '')
      setJobs([]); setComparison(null); setExportCode(''); setStep(1)
      pendingCalculation.current = null
    }
  })
  const calculate = (changes: Poe2Changes = {}) => perform(async active => {
    const signature = JSON.stringify({buildId: selected, changes})
    if (pendingCalculation.current?.signature !== signature) pendingCalculation.current = {signature, key: crypto.randomUUID()}
    const job = value(await wowApi.poe2.calculate({buildId: selected, changes, idempotencyKey: pendingCalculation.current.key}, auth))
    if (!active()) return
    pendingCalculation.current = null
    setJobs(current => [job, ...current.filter(item => item.id !== job.id)])
  })
  const candidateChanges = (): Poe2Changes => {
    if (editKind === 'item') return {items: [{slot, text: itemText}]}
    if (editKind === 'level') return {level: Number(level)}
    if (editKind === 'config') return {config: {enemyIsBoss: boss}}
    if (editKind === 'passive') return {[nodeAction]: nodes.split(/[,，\s]+/u).filter(Boolean).map(Number)}
    if (editKind === 'group') return {mainSocketGroup: Number(group)}
    return {skillGroups: [{index: Number(group), gems: gems.split('\n').filter(line => line.trim()).map(line => {
      const parts = line.trim().split('|'); return {name: poe2GemInput(parts[0]?.trim() ?? ''), level: Number(parts[1] || 1), quality: Number(parts[2] || 0)}
    })}]}
  }
  return <section className={styles['workbench']} aria-label="POE2 构筑工作台">
    <aside className={styles['sidebar']}>
      <h2>我的构筑</h2>
      <p>国际服 PoB 2 · 中文助手</p>
      {!builds.length ? <p>导入 PoB 2 构筑，开始诊断与比较。</p> : null}
      <button type="button" disabled={busy} onClick={() => {selectionEpoch.current++; setSelected(''); setSource(''); setTitle(''); setError(''); setStep(1)}}>＋ 导入新构筑</button>
      {builds.map(build => <div key={build.id} className={styles['buildItem']} data-active={build.id === selected}>
        <button className={styles['buildSelect']} type="button" disabled={busy} aria-pressed={build.id === selected} onClick={() => {selectionEpoch.current++; setSelected(build.id); setDeleteTarget(''); setStep(1)}}>
          <span className={styles['buildName']}>{build.title}</span>
          <span className={styles['buildIdentity']}>{[
            typeof build.summary['className'] === 'string' ? poe2Term(build.summary['className'], 'class') : '',
            typeof build.summary['ascendancy'] === 'string' && build.summary['ascendancy'] !== 'None' ? poe2Term(build.summary['ascendancy'], 'ascendancy') : '',
            typeof build.summary['level'] === 'number' ? `${build.summary['level']} 级` : '',
          ].filter(Boolean).join(' · ')}</span>
          <span className={styles['buildDate']}>导入于 {new Date(build.createdAt).toLocaleString('zh-CN', {month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'})}</span>
        </button>
        <button className={styles['buildDelete']} type="button" disabled={busy} aria-label={`删除构筑：${build.title}`} title="删除构筑" onClick={() => setDeleteTarget(build.id)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg>
        </button>
        {deleteTarget === build.id ? <div className={styles['deleteConfirm']} role="group" aria-label="确认删除构筑">
          <p>删除此构筑？它将从列表中移除。</p>
          <button type="button" disabled={busy} onClick={() => setDeleteTarget('')}>取消</button>
          <button type="button" disabled={busy} onClick={() => void deleteBuild(build.id)}>{busy ? '删除中…' : '确认删除'}</button>
        </div> : null}
      </div>)}
    </aside>
    <div className={styles['content']}>
      <header><p className={styles['eyebrow']}>PATH OF EXILE 2</p><h1>构筑工作台</h1><p>导入查看完整构筑，再比较调整效果。</p></header>
      <nav className={styles['steps']} aria-label="构筑操作步骤">
        {['① 导入', '② 对比'].map((label, index) => <button key={label} type="button" aria-current={step === index + 1 ? 'step' : undefined} disabled={busy || (index === 1 && !activeBuild)} onClick={() => setStep(index + 1)}>{label}</button>)}
      </nav>
      {error ? <div role="alert" className={styles['error']}>{errorMessage(error)}</div> : null}
      {step === 1 ? <section className={styles['card']} aria-label="导入构筑指引">
        <h2>第一步 · 导入构筑</h2>
        <p>导入 PoB 2 字符串，直接查看角色、属性、天赋和技能。</p>
        {activeBuild ? <section className={styles['parsedCharacter']} aria-label="已解析角色">
          <div className={styles['characterHeader']}>
            <h3>角色解析成功</h3>
            <div className={styles['buildIdGroup']}>
              <span className={styles['buildIdLabel']}>构筑 ID</span>
              <code className={styles['buildIdValue']}>{activeBuild.id}</code>
              <button type="button" className={styles['copyId']} onClick={async () => {
                const epoch = selectionEpoch.current
                try {
                  await navigator.clipboard.writeText(activeBuild.id)
                  if (epoch === selectionEpoch.current) setCopyStatus('已复制，可粘贴到鸡哥对话中')
                } catch {
                  if (epoch === selectionEpoch.current) setCopyStatus('复制失败，请选中构筑 ID 手动复制')
                }
              }}>复制 ID</button>
              {copyStatus ? <span className={styles['copyStatus']} role="status">{copyStatus}</span> : null}
            </div>
          </div>
          <dl className={styles['preview']}>
            {typeof activeBuild.summary['level'] === 'number' ? <div><dt className={styles['characterLabel']}>角色等级</dt><dd className={styles['characterValue']}>{activeBuild.summary['level']} 级</dd></div> : null}
            {typeof activeBuild.summary['className'] === 'string' && activeBuild.summary['className'] ? <div><dt className={styles['characterLabel']}>职业</dt><dd className={styles['characterValue']}>{poe2Term(activeBuild.summary['className'], 'class')}</dd></div> : null}
            {typeof activeBuild.summary['ascendancy'] === 'string' && activeBuild.summary['ascendancy'] ? <div><dt className={styles['characterLabel']}>升华</dt><dd className={styles['characterValue']}>{poe2Term(activeBuild.summary['ascendancy'], 'ascendancy')}</dd></div> : null}
          </dl>
        </section> : <>
        <div className={styles['guide']}>
          <h3>如何获取 PoB 字符串？</h3>
          <div className={styles['importMethods']}>
            <div className={styles['importMethod']}><strong className={styles['methodTitle']}>从 poe.ninja 复制</strong><p className={styles['methodText']}>打开 <a href="https://poe.ninja/poe2/builds" target="_blank" rel="noreferrer">POE2 角色页 ↗</a>，在 <span className={styles['menuName']}>IMPORT CODE FOR PATH OF BUILDING</span> 区域复制导入码。</p></div>
            <div className={styles['importMethod']}><strong className={styles['methodTitle']}>从 PoB 2 导出</strong><p className={styles['methodText']}>打开 <span className={styles['menuName']}>Import/Export Build（导入/导出）</span>，生成并复制构筑字符串。</p></div>
          </div>
          <div className={styles['guideFooter']}><span>复制后，粘贴到下方即可导入。</span><a href="https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2" target="_blank" rel="noreferrer">PoB 2 项目 ↗</a><a href="https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases" target="_blank" rel="noreferrer">下载 PoB 2 ↗</a></div>
        </div>
        <label data-poe2-field>构筑名称（可选，仅用于管理）<input data-poe2-input value={title} maxLength={128} onChange={e => setTitle(e.target.value)} /></label>
        <label data-poe2-field>PoB 2 字符串<textarea data-poe2-input data-poe2-textarea aria-label="构筑分享码" value={source} maxLength={2000000} rows={6} disabled={busy} onChange={e => setSource(e.target.value)} /></label>
        <button type="button" disabled={busy} onClick={() => void importBuild()}>{busy ? '正在导入…' : '导入构筑'}</button>
        </>}
      </section> : null}
      {activeBuild && step !== 1 ? <section className={styles['buildSummary']}><h2>{activeBuild.title}</h2><p>{poe2Term(String(activeBuild.summary['className'] ?? ''), 'class')} · {poe2Term(String(activeBuild.summary['ascendancy'] ?? ''), 'ascendancy')} · {String(activeBuild.summary['level'] ?? '—')} 级 · 树版本 {activeBuild.gameVersion || '未标记'} · 赛季 {activeBuild.league || '未标记'}</p></section> : null}
      {activeBuild && step === 1 && !baseline?.result ? <section className={styles['card']} role="status"><h2>角色属性与技能</h2><p>{overviewLoading || pending ? '正在读取构筑详情…' : '构筑详情暂未生成。'}</p>{!overviewLoading && !pending ? <button type="button" disabled={busy} onClick={() => void calculate()}>重新读取构筑详情</button> : null}</section> : null}
      {activeBuild && step === 2 ? <>
        <h2>第二步 · 对比</h2><p>选择一项调整，与导入时的原始构筑自动对比。</p>
        <div className={styles['actions']}>
          {!baselineId && !overviewLoading && !pending ? <button type="button" disabled={calculating} onClick={() => void calculate()}>重新读取原始构筑</button> : null}
          <span role="status">{baseline ? `原始构筑：${stateLabels[baseline.status]}` : '尚未计算原始构筑'}</span>
        </div>
        <details className={styles['card']} open><summary>建立对比方案</summary>
          <p>每个方案从原始构筑出发。只调整想比较的内容，其余设置保持一致。</p>
          <label data-poe2-field>调整内容<select data-poe2-input value={editKind} onChange={e => setEditKind(e.target.value)}>
            <option value="item">替换装备</option><option value="gems">调整技能与辅助</option><option value="group">选择主技能组</option><option value="passive">调整天赋节点</option><option value="config">敌人配置</option><option value="level">角色等级</option>
          </select></label>
          {editKind === 'item' ? <><label data-poe2-field>装备槽位<select data-poe2-input value={slot} onChange={e => setSlot(e.target.value)}>{Object.entries(poe2Slots).map(([name, label]) => <option key={name} value={name}>{label}</option>)}</select></label><label data-poe2-field>装备文本<textarea aria-label="装备文本" data-poe2-input data-poe2-textarea rows={5} value={itemText} onChange={e => setItemText(e.target.value)} placeholder="粘贴游戏中复制的装备文本" /></label></> : null}
          {editKind === 'level' ? <label data-poe2-field>等级<input data-poe2-input type="number" min={1} max={100} value={level} onChange={e => setLevel(e.target.value)} /></label> : null}
          {editKind === 'group' || editKind === 'gems' ? <label data-poe2-field>技能组序号<input data-poe2-input type="number" min={1} max={100} value={group} onChange={e => setGroup(e.target.value)} /></label> : null}
          {editKind === 'gems' ? <><label data-poe2-field>替换此组的技能和辅助（每行：国服名称 | 等级 | 品质）<textarea data-poe2-input data-poe2-textarea rows={5} value={gems} onChange={e => setGems(e.target.value)} placeholder={'盾墙 | 20 | 0'} /></label><p>支持已核实的国服名称和 PoB 原文名称，请保留辅助宝石的罗马阶级。未收录名称需先核实。</p></> : null}
          {editKind === 'config' ? <label data-poe2-field>敌人类型<select data-poe2-input value={boss} onChange={e => setBoss(e.target.value)}><option value="None">普通敌人</option><option value="Boss">首领</option><option value="Pinnacle">巅峰首领</option></select></label> : null}
          {editKind === 'passive' ? <><label data-poe2-field>节点操作<select data-poe2-input value={nodeAction} onChange={e => setNodeAction(e.target.value)}><option value="allocateNodes">分配节点及连接路径</option><option value="deallocateNodes">取消节点</option></select></label><label data-poe2-field>天赋节点 ID（逗号分隔）<input data-poe2-input value={nodes} onChange={e => setNodes(e.target.value)} /></label></> : null}
          <button type="button" disabled={calculating || !baselineId} onClick={() => {try {void calculate(candidateChanges())} catch (e) {setError(e instanceof Error ? e.message : '技能名称待核实')}}}>计算方案</button>
          {!baselineId ? <p>原始构筑详情就绪后即可计算方案。</p> : null}
          {pending ? <p role="status">云端正在计算，请稍候…</p> : null}
        </details>
        {baseline?.errorCode || candidate?.errorCode ? <p role="alert">{errorMessage(baseline?.errorCode || candidate?.errorCode || '')} 修改输入后可重新计算。</p> : null}
        {comparing ? <p role="status">正在生成对比结果…</p> : null}
        {baselineId && candidateId && !comparison && !comparing ? <button type="button" onClick={() => {setError(''); setCompareRetry(v => v + 1)}}>重新加载对比</button> : null}
        {comparison ? <section className={styles['card']}><h2>方案对比</h2><p>按选择顺序：基线 → 候选。结果适用于各自记录的配置。</p><p>基线：{describeChanges(comparison.baselineChanges)}</p><p>候选：{describeChanges(comparison.candidateChanges)}</p><table><thead><tr><th>指标</th><th>基线</th><th>候选</th><th>变化</th></tr></thead><tbody>{Object.entries(comparison.metrics).filter(([key]) => key in labels).map(([key, metric]) => <tr key={key}><td>{labels[key]}</td><td>{number(metric.baseline)}</td><td>{number(metric.candidate)}</td><td>{metric.percent === null ? number(metric.delta) : `${number(metric.percent)}%`}</td></tr>)}</tbody></table></section> : null}
        <div className={styles['actions']}><button type="button" disabled={busy} onClick={() => setStep(1)}>返回原始构筑</button></div>
      </> : null}
      {activeBuild && step === 1 && resultJob?.result ? <section className={styles['card']} aria-label="构筑详情"><h2>角色属性与技能</h2>
          <p>以下为所选方案在记录的配置条件下的理论结果。</p><div className={styles['metrics']}>{Object.entries(resultJob.result.stats).filter(([key]) => key in labels).map(([key, n]) => <div key={key}><small>{labels[key]}</small><strong>{number(n)}</strong></div>)}</div>
          <Poe2SkillCards result={resultJob.result} />
          <div className={styles['actions']}><button type="button" onClick={() => setExportCode(resultJob.result!.exportCode)}>导出此方案</button><button type="button" disabled={busy} onClick={() => void perform(async active => {const code = value(await wowApi.poe2.exportBuild(selected, auth)).exportCode; if (active()) setExportCode(code)})}>导出原始构筑</button></div>
        </section> : null}
      {activeBuild && step === 1 ? <Poe2PassiveTree auth={auth} buildId={activeBuild.id} /> : null}
      {step === 1 && exportCode ? <section className={styles['card']}><h2>PoB 2 分享码</h2><textarea data-poe2-input data-poe2-textarea readOnly rows={4} aria-label="导出的构筑" value={exportCode} onFocus={e => e.target.select()} /><p>复制后可在 PoB 2 中导入。</p></section> : null}
      <p className={styles['notice']}>本工具由社区独立开发，与 Grinding Gear Games 无关联，亦未获其背书。</p>
    </div>
  </section>
}
