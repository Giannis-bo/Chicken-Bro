import { useEffect, useRef, useState } from 'react'
import { wowApi, type AdminClient, type ClientAuthContext } from '@wow-mini/api-client'
import type { AdminAccess, AdminGame, AdminOverview } from '@wow-mini/domain'
import { webViewHref } from './web-routing'
import styles from './WebAdmin.module.scss'

type Auth = Extract<ClientAuthContext, { kind: 'web' }>
export function beijingDate(now = new Date()): string { return new Date(now.getTime() + 8 * 3600000).toISOString().slice(0,10) }
export function presetDates(days: number, now = new Date()): [string,string] {
  const end = beijingDate(now)
  return [new Date(Date.parse(`${end}T00:00:00Z`) - (days-1)*86400000).toISOString().slice(0,10), end]
}
export const formatRate = (n: number | null): string => n === null ? '—' : `${(n*100).toFixed(1)}%`
const number = (n: number) => n.toLocaleString('zh-CN')
const duration = (n: number | null) => n === null ? '—' : n < 60 ? `${n.toFixed(1)} 秒` : `${(n/60).toFixed(1)} 分钟`
function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return <div className={styles['stat']}><span>{label}</span><strong>{value}</strong>{hint ? <small>{hint}</small> : null}</div>
}
function Metric({ label, value }: { label: string; value: string }) { return <div className={styles['metric']}><dt>{label}</dt><dd>{value}</dd></div> }
const classNames: Record<string,string> = { warrior:'战士',paladin:'圣骑士',hunter:'猎人',rogue:'潜行者',priest:'牧师',shaman:'萨满祭司',mage:'法师',warlock:'术士',monk:'武僧',druid:'德鲁伊',evoker:'唤魔师',death_knight:'死亡骑士',demon_hunter:'恶魔猎手',unknown:'未知' }
const specNames: Record<string,string> = { arms:'武器',fury:'狂怒',protection:'防护',retribution:'惩戒',holy:'神圣',beast_mastery:'野兽控制',marksmanship:'射击',survival:'生存',assassination:'奇袭',outlaw:'狂徒',subtlety:'敏锐',discipline:'戒律',shadow:'暗影',elemental:'元素',enhancement:'增强',restoration:'恢复',arcane:'奥术',fire:'火焰',frost:'冰霜',affliction:'痛苦',demonology:'恶魔学识',destruction:'毁灭',brewmaster:'酒仙',mistweaver:'织雾',windwalker:'踏风',balance:'平衡',feral:'野性',guardian:'守护',devastation:'湮灭',preservation:'恩护',augmentation:'增辉',blood:'鲜血',unholy:'邪恶',havoc:'浩劫',vengeance:'复仇',unknown:'未知' }
const localName = (value: string, names: Record<string,string>) => names[value.toLowerCase().replace(/[- ]/gu,'_')] ?? value

export default function WebAdmin({auth,accountLabel,onLogout,client=wowApi.admin}: {auth: Auth; accountLabel: string; onLogout: () => void; client?: AdminClient}) {
  const [game,setGame]=useState<AdminGame>('wow')
  const [access,setAccess]=useState<AdminAccess | null>(null)
  const [data,setData]=useState<AdminOverview | null>(null)
  const [range,setRange]=useState<[string,string]>(()=>presetDates(7))
  const [draft,setDraft]=useState<[string,string]>(()=>presetDates(7))
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(true)
  const [refresh,setRefresh]=useState(0)
  const [series,setSeries]=useState<'activeUsers'|'questions'|'simulations'|'builds'>('activeUsers')
  const sequence=useRef(0)
  useEffect(()=>{
    let alive=true
    const load=async()=>{
      const intent=++sequence.current
      setBusy(true); setError(''); setData(null)
      try {
        const a=await client.access(auth)
        if (!alive || intent!==sequence.current) return
        if(a.fromFallback || !a.payload) { setAccess(null); setError(a.httpStatus===401 ? '登录已失效，请退出后重新使用 QQ 登录。' : '无法检查后台权限，请稍后重试。'); return }
        setAccess(a.payload)
        if(!a.payload.isAdmin) return
        const result=await client.overview(auth,...range,game)
        if(!alive || intent!==sequence.current) return
        if(result.fromFallback || !result.payload || result.payload.game !== game) {
          if(result.httpStatus===403 || result.httpStatus===401) setAccess(null)
          setError(result.problemCode==='ADMIN_DATE_INVALID' ? '日期范围无效，最多可查询 366 天，结束日期不能晚于今天。' : result.httpStatus===403 ? '此账号没有后台权限。' : result.httpStatus===401 ? '登录已失效，请退出后重新登录。' : '统计数据暂不可用，请稍后重试。'); return
        }
        setData(result.payload)
      } catch { if(alive) { setData(null); setError('网络请求失败，请稍后重试。') } }
      finally { if(alive && intent===sequence.current) setBusy(false) }
    }
    void load()
    return ()=>{alive=false}
  },[auth,client,range,refresh,game])
  const selectRange=(days:number)=>{const next=presetDates(days);setDraft(next);setRange(next)}
  const apply=()=>{
    if(!draft[0] || !draft[1] || draft[0]>draft[1] || draft[1]>beijingDate() || Date.parse(draft[1])-Date.parse(draft[0])>=366*86400000) { setError('请选择有效日期，范围最多 366 天，结束日期不能晚于今天。'); return }
    setRange([...draft])
  }
  const tasks=data?.game==='wow' ? data.simc : data?.poe2
  const taskLabel=game==='wow' ? '模拟任务' : '计算任务'
  const gameLabel=game==='wow' ? '魔兽世界' : 'POE2'
  const max=Math.max(1,...(data?.daily.map(d=>d[series])??[]))
  return <main className={styles['admin']}>
    <header className={styles['header']}><a className={styles['brand']} href={webViewHref('chat')}>炸鸡队长来啦<span>运营后台</span></a><div className={styles['account']}><span>{accountLabel}</span><a href={webViewHref('chat')}>返回网站</a><button className={styles['control']} onClick={onLogout}>退出登录</button></div></header>
    <div className={styles['content']}>
      <div className={styles['heading']}><div><p className={styles['eyebrow']}>CHICKENBRO / OPERATIONS</p><h1>运营概览</h1><p>分游戏查看用户活跃、回答质量与计算表现。</p></div><span className={styles['badge']}>只读 · 管理员专属</span></div>
      {error ? <div className={styles['notice']} role="alert">{error}<button className={styles['control']} onClick={()=>setRefresh(v=>v+1)}>重试</button></div> : null}
      {busy ? <p role="status" className={styles['notice']}>正在读取运营数据…</p> : null}
      {!busy && access && !access.isAdmin ? <section className={styles['denied']}><h2>此账号没有后台访问权限</h2><p>运营后台仅向已核验的管理员开放。</p><details><summary>查看当前账号核验标识</summary><code>{access.accountId}</code><p>这是当前登录账号的内部标识，不是密码；不会自动获得管理员权限。</p></details></section> : null}
      {access?.isAdmin ? <>
        <nav className={styles['gameTabs']} aria-label="游戏模块">{(['wow','poe2'] as const).map(value=><button key={value} className={styles['control']} aria-pressed={game===value} onClick={()=>{if(value!==game){setData(null);setGame(value);setSeries('activeUsers')}}}>{value==='wow' ? '魔兽世界' : 'POE2'}</button>)}</nav>
        <section className={styles['filters']} aria-label="统计日期"><div className={styles['presets']}>{[[1,'今天'],[7,'近 7 天'],[30,'近 30 天']].map(([days,label])=><button className={styles['control']} key={days} aria-pressed={range.join()===presetDates(Number(days)).join()} onClick={()=>selectRange(Number(days))}>{label}</button>)}</div><div className={styles['dates']}><label>开始日期<input className={styles['dateInput']} aria-label="开始日期" type="date" value={draft[0]} max={beijingDate()} onChange={e=>setDraft([e.target.value,draft[1]])} /></label><span>—</span><label>结束日期<input className={styles['dateInput']} aria-label="结束日期" type="date" value={draft[1]} max={beijingDate()} onChange={e=>setDraft([draft[0],e.target.value])} /></label><button className={styles['control']} onClick={apply}>查询</button><button className={styles['control']} disabled={busy} onClick={()=>setRefresh(v=>v+1)}>刷新</button></div></section>
        {data && tasks ? <>
          <div className={styles['snapshot']}><span>{gameLabel} · {data.start} — {data.end} · 北京时间</span><span>更新于 {new Date(data.generatedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}</span></div>
          <section className={styles['stats']} aria-label="核心指标"><Stat label="累计用户" value={number(data.users.total)} hint="全站 · 截至结束日的 QQ 用户"/><Stat label="新增用户" value={number(data.users.new)} hint="全站 · 期间首次 QQ 登录"/><Stat label="活跃用户" value={number(data.users.active)} hint="当前游戏 · 提问、导入或计算去重"/><Stat label="提问数" value={number(data.chat.total)} hint="所选期间发起的回复"/><Stat label={taskLabel} value={number(tasks.total)} hint="含网站与对话工具提交"/></section>
          <section className={styles['panel']}><div className={styles['panelTitle']}><div><h2>使用趋势</h2><p>每日统计，缺少记录的日期显示为 0</p></div><div className={styles['presets']}>{([['activeUsers','活跃用户'],['questions','提问数'],['simulations',taskLabel],...(game==='poe2' ? [['builds','构筑导入']] as const : [])] as const).map(([key,label])=><button className={styles['control']} key={key} aria-pressed={series===key} onClick={()=>setSeries(key)}>{label}</button>)}</div></div>
            <div className={styles['chart']} role="img" aria-label="每日使用趋势，精确数据见下方明细"><span className={styles['chartMax']}>{max}</span><div className={styles['bars']}>{data.daily.map(d=><div className={styles['barColumn']} key={d.date} title={`${d.date}：${d[series]}`}><div className={styles['bar']} style={{height:`${d[series]/max*100}%`}}/><span>{data.daily.length<=31 ? d.date.slice(5) : ''}</span></div>)}</div></div>
            <details className={styles['details']}><summary>查看每日明细</summary><div className={styles['tableWrap']}><table><thead><tr><th>日期</th><th>新增用户</th><th>活跃用户</th><th>提问数</th><th>{taskLabel}</th>{game==='poe2' ? <th>构筑导入</th> : null}</tr></thead><tbody>{data.daily.map(d=><tr key={d.date}><td>{d.date}</td><td>{d.newUsers}</td><td>{d.activeUsers}</td><td>{d.questions}</td><td>{d.simulations}</td>{game==='poe2' ? <td>{d.builds}</td> : null}</tr>)}</tbody></table></div></details>
          </section>
          <div className={styles['grid']}>
            <section className={styles['panel']}><h2>{gameLabel} · 鸡哥对话</h2><div className={styles['featureStats']}><Stat label="回复成功率" value={formatRate(data.chat.successRate)}/><Stat label="反馈解决率" value={formatRate(data.chat.resolutionRate)}/></div><dl><Metric label="成功 / 失败 / 进行中" value={`${data.chat.succeeded} / ${data.chat.failed} / ${data.chat.running}`}/><Metric label="已解决 / 未解决" value={`${data.chat.resolved} / ${data.chat.unresolved}`}/><Metric label="反馈率" value={formatRate(data.chat.feedbackRate)}/><Metric label="平均 / P95 回复耗时" value={`${duration(data.chat.avgSeconds)} / ${duration(data.chat.p95Seconds)}`}/></dl><p className={styles['footnote']}>成功率以已结束回复为分母；反馈率以成功回复为分母；解决率仅代表已提交反馈的回复。</p></section>
            <section className={styles['panel']}><h2>{game==='wow' ? 'SimC 模拟' : 'PoB 构筑计算'}</h2><div className={styles['featureStats']}><Stat label={game==='wow' ? '模拟成功率' : '计算成功率'} value={formatRate(tasks.successRate)}/><Stat label="排队 / 运行中" value={`${tasks.queued} / ${tasks.running}`}/></div><dl><Metric label="成功 / 失败 / 取消" value={`${tasks.succeeded} / ${tasks.failed} / ${tasks.cancelled}`}/><Metric label="结果异常" value={number(tasks.invalidResults)}/><Metric label="平均 / P95 完成耗时" value={`${duration(tasks.avgSeconds)} / ${duration(tasks.p95Seconds)}`}/></dl><p className={styles['footnote']}>成功要求有效指标和来源记录。成功率分母包含成功、失败及结果异常；耗时含排队，仅统计已结束任务。</p></section>
          </div>
          {game==='wow' ? <section className={styles['panel']}><h2>职业与专精分布</h2><p className={styles['footnote']}>按模拟任务来源角色统计，每个任务计一次。</p>{data.specializations.length ? <div className={styles['tableWrap']}><table><thead><tr><th>职业</th><th>专精</th><th>任务数</th><th>占比</th></tr></thead><tbody>{data.specializations.map(row=><tr key={`${row.class}/${row.spec}`}><td>{localName(row.class,classNames)}</td><td>{localName(row.spec,specNames)}</td><td>{number(row.count)}</td><td>{formatRate(row.count/tasks.total)}</td></tr>)}</tbody></table></div> : <p className={styles['empty']}>所选期间暂无模拟任务</p>}</section> : <section className={styles['panel']}><h2>POE2 构筑</h2><div className={styles['featureStats']}><Stat label="构筑导入" value={number(data.builds)} hint="所选期间保存的构筑，含已删除记录"/><Stat label="计算任务" value={number(tasks.total)} hint="基线与方案计算；复用不重复计数"/></div>{!data.builds && !tasks.total ? <p className={styles['empty']}>所选期间暂无构筑导入或计算任务</p> : null}</section>}
          <footer className={styles['method']}><strong>统计口径</strong><p>仅统计当前 QQ 应用关联用户，排除固定测试账号、已知模拟验收身份及无 QQ 身份的历史记录。累计／新增 QQ 用户为全站账号数据；对话、活跃用户与任务仅统计当前游戏，活跃用户按期间去重（POE2 含构筑导入）；各业务按发起日期归入所选期间，展示查询时的最新状态和反馈。归档会话仍计入。没有样本的比例或耗时显示「—」。页面访问量、Token 和费用尚未纳入。</p></footer>
        </> : null}
      </> : null}
    </div>
  </main>
}
