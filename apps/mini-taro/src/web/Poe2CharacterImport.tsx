import {useEffect, useRef, useState} from 'react'
import {wowApi, type ClientAuthContext, type ApiResult} from '@wow-mini/api-client'
import type {Poe2Import, Poe2ImportProvider, Poe2ImportIssue} from '@wow-mini/domain'
import styles from './WebPoe2.module.scss'

type Auth = Extract<ClientAuthContext, {kind: 'web'}>
const statuses: Record<Poe2Import['status'], string> = {queued: '等待读取', fetching: '读取公开角色资料', mapping: '检查角色映射', validating: '验证构筑与计算基线', ready: '基线已完成', needs_input: '需要补充完整 PoB 构筑', blocked: '来源暂不可用', failed: '导入失败', cancelled: '已取消导入'}
const pending = (p: Poe2Import) => ['queued', 'fetching', 'mapping', 'validating'].includes(p.status)
const messages: Record<string, string> = {POE2_SOURCE_PROVIDER_MISMATCH: '链接与所选来源不符，请切换正确入口。', POE2_SOURCE_URL_INVALID: '链接格式不正确，请按示例复制完整角色链接。', AUTH_REQUIRED: '登录已失效，请重新登录。', POE2_IMPORT_ACTIVE: '已有导入任务进行中，请先恢复或取消该任务。'}
const result = (r: ApiResult<Poe2Import | null>) => {if (r.fromFallback || !r.payload) throw new Error(r.problemCode || '读取失败，请重试'); return r.payload}
export function validCharacterUrl(value: string, provider: Poe2ImportProvider): boolean {
  try {
    const url = new URL(value.trim())
    if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search) return false
    if (provider === 'wegame') return url.hostname === 'www.wegame.com.cn' && url.pathname === '/helper/poe2/' && /^#\/share\/[A-Za-z0-9_-]+$/u.test(url.hash)
    if (url.hostname !== 'poe.ninja' || url.hash) return false
    const match = /^\/poe2\/profile\/([^/]+)\/([^/]+)\/character\/([^/]+)$/u.exec(url.pathname)
    return Boolean(match && match.slice(1).every(part => {const s = decodeURIComponent(part); return s && !['.', '..'].includes(s) && !/[\\%?#/]/u.test(s) && Array.from(s).every(char => char.charCodeAt(0) >= 32 && char.charCodeAt(0) !== 127)}))
  } catch {return false}
}
const issueGroup = (issue: Poe2ImportIssue) => {
  if (/JEWEL/u.test(issue.code)) return '珠宝资料缺失或尚未支持'
  if (/SKILL|GEM/u.test(issue.code)) return '技能资料不足或尚未支持'
  if (/ITEM|MOD|BASE|UNIQUE|RUNE|CHARM|FLASK|EQUIPMENT/u.test(issue.code)) return '装备或词缀尚未支持'
  if (/VERSION|QUEST|PENALTY/u.test(issue.code)) return '版本或任务信息待确认'
  return '其他资料待补充'
}
const display = (v: unknown) => v === 'incomplete' ? '资料不完整，需补充' : v === 'complete' ? '资料检查通过' : typeof v === 'string' || typeof v === 'number' ? String(v) : '未提供'

export default function Poe2CharacterImport({auth, onReady}: {auth: Auth; onReady: (buildId: string, baselineJobId: string) => Promise<void | boolean> | void | boolean}) {
  const [provider, setProvider] = useState<Poe2ImportProvider>('wegame')
  const [url, setUrl] = useState('')
  const [source, setSource] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [packet, setPacket] = useState<Poe2Import | null>(null)
  const [busy, setBusy] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [error, setError] = useState('')
  const [storageNotice, setStorageNotice] = useState('正在准备同会话恢复…')
  const [recoveryIds, setRecoveryIds] = useState<string[]>([])
  const authGeneration = useRef(0)
  const generation = useRef(0)
  const activeImport = useRef<string | null>(null)
  const identity = useRef(auth.csrfToken)
  const storageKey = useRef<string | null>(null)
  const lock = useRef(false)
  const callback = useRef(onReady); callback.current = onReady
  const delivered = useRef('')
  const actionKey = useRef<{signature: string; key: string} | null>(null)
  if (identity.current !== auth.csrfToken) {identity.current = auth.csrfToken; authGeneration.current++; generation.current++; storageKey.current = null; activeImport.current = null; lock.current = false}
  const persist = (id: string) => {
    if (storageKey.current) try {sessionStorage.setItem(storageKey.current, id)} catch {setStorageNotice('浏览器存储不可用，本次无法自动恢复；可重试读取。')}
  }
  const accept = (p: Poe2Import) => {
    activeImport.current = p.id
    setPacket(p)
    persist(p.id)
  }
  useEffect(() => {
    const life = ++authGeneration.current
    const g = ++generation.current
    let disposed = false
    setPacket(null); setUrl(''); setSource(''); setConfirmed(false); setBusy(false); setCompleting(false); setError(''); setProvider('wegame'); delivered.current = ''; actionKey.current = null
    storageKey.current = null
    activeImport.current = null; setRecoveryIds([])
    void (async () => {
      try {
        if (!auth.csrfToken || !crypto.subtle) throw new Error('no session fingerprint')
        const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(auth.csrfToken))
        if (disposed || authGeneration.current !== life) return
        const key = 'poe2-import:' + Array.from(new Uint8Array(hash), n => n.toString(16).padStart(2, '0')).join('')
        const saved = sessionStorage.getItem(key)
        storageKey.current = key; setStorageNotice('仅恢复同一登录会话中的导入进度。')
        if (activeImport.current) persist(activeImport.current)
        if (saved && generation.current === g) {
          const p = result(await wowApi.poe2.getImport(saved, auth))
          if (disposed || authGeneration.current !== life || generation.current !== g || p.id !== saved) return
          setProvider(p.provider); accept(p)
        }
      } catch (e) {if (generation.current === g) {setStorageNotice('自动恢复不可用，可重新读取或重试。'); setError(e instanceof Error && e.message !== 'no session fingerprint' ? e.message : '')}}
    })()
    return () => {disposed = true; authGeneration.current++; generation.current++}
  }, [auth.csrfToken])
  useEffect(() => {
    if (!packet || !pending(packet) || busy) return
    const g = generation.current
    let disposed = false
    const current = () => !disposed && generation.current === g && activeImport.current === packet.id
    const timer = window.setTimeout(() => {
      void wowApi.poe2.getImport(packet.id, auth).then(result).then(p => {if (current() && p.id === packet.id) accept(p)}).catch(e => {if (current()) setError(String(e.message))})
    }, 2000)
    return () => {disposed = true; window.clearTimeout(timer)}
  }, [packet, auth.csrfToken, busy])
  useEffect(() => {
    if (!packet || packet.status !== 'ready' || !packet.buildId || !packet.baselineJobId || delivered.current === packet.id) return
    const g = generation.current; delivered.current = packet.id
    const completedKey = storageKey.current
    setCompleting(true)
    void Promise.resolve(callback.current(packet.buildId, packet.baselineJobId)).then(accepted => {
      // Successful delivery may already have unmounted this component. Consume
      // only the captured session's matching record, never a newer import.
      if (accepted === false || !completedKey) return
      try {if (sessionStorage.getItem(completedKey) === packet.id) sessionStorage.removeItem(completedKey)} catch {if (g === generation.current) setStorageNotice('浏览器存储不可用，无法清除已完成的恢复记录。')}
    }).catch(e => {if (g === generation.current) {delivered.current = ''; setError(String(e.message))}}).finally(() => {if (g === generation.current) setCompleting(false)})
  }, [packet])
  const cancelAbandoned = async (id: string, life: number) => {
    if (authGeneration.current !== life) return
    try {
      const p = result(await wowApi.poe2.cancelImport(id, auth))
      if (p.id !== id || p.status !== 'cancelled') throw new Error('cancel not confirmed')
      if (authGeneration.current === life) setRecoveryIds(ids => ids.filter(saved => saved !== id))
    } catch {
      if (authGeneration.current !== life) return
      setRecoveryIds(ids => ids.includes(id) ? ids : [...ids, id])
      if (!activeImport.current) persist(id)
    }
  }
  const run = async (operation: (key: string) => Promise<ApiResult<Poe2Import | null>>, signature: string) => {
    if (lock.current) return
    lock.current = true; const g = ++generation.current; const life = authGeneration.current
    setBusy(true); setError('')
    if (actionKey.current?.signature !== signature) actionKey.current = {signature, key: crypto.randomUUID()}
    try {
      const p = result(await operation(actionKey.current.key))
      if (generation.current !== g) {
        // A source switch abandons this source job; an account change must not
        // perform any follow-up using the previous account's credentials.
        if (authGeneration.current === life && pending(p)) void cancelAbandoned(p.id, life)
        return
      }
      actionKey.current = null; setSource(''); setConfirmed(false); setProvider(p.provider); accept(p)
      setRecoveryIds(ids => ids.filter(id => id !== p.id))
    } catch (e) {if (generation.current === g) setError(e instanceof Error ? e.message : '请求失败，请重试')}
    finally {if (generation.current === g) {lock.current = false; setBusy(false)}}
  }
  const switchSource = (next: Poe2ImportProvider) => {
    if (next === provider) return
    const abandoned = packet
    generation.current++; lock.current = false; actionKey.current = null; delivered.current = ''
    setProvider(next); setUrl(''); setSource(''); setConfirmed(false); setPacket(null); setBusy(false); setError('')
    activeImport.current = null
    if (abandoned && pending(abandoned)) {
      void cancelAbandoned(abandoned.id, authGeneration.current)
    }
  }
  const groups = new Map<string, Poe2ImportIssue[]>()
  for (const issue of packet?.issues ?? []) {const key = issueGroup(issue); groups.set(key, [...(groups.get(key) ?? []), issue])}
  const valid = validCharacterUrl(url, provider)
  const taskSource = packet?.preview?.['sourceUrl']
  const ninjaSource = packet?.provider === 'ninja' && typeof taskSource === 'string' && validCharacterUrl(taskSource, 'ninja') ? taskSource.trim() : null
  return <section aria-label="角色链接导入" className={styles['characterImport']}>
    <div className={styles['sourceTabs']} aria-label="角色来源">{(['wegame', 'ninja'] as const).map(p => <button type="button" key={p} disabled={completing} aria-pressed={provider === p} onClick={() => switchSource(p)}>{p === 'wegame' ? '国服 · WeGame' : '国际服 · poe.ninja'}</button>)}</div>
    {completing ? <p role="status">正在加载已完成的构筑和基线，完成后可切换来源。</p> : null}
    {provider === 'wegame' ? <p>在 WeGame 角色助手复制公开分享链接。当前仅支持有限映射，珠宝、技能、装备词缀或版本资料缺失时，需要补充完整 PoB 构筑。</p> : <p>复制 poe.ninja 角色链接后，请打开该角色页，使用 Copy PoB 复制完整代码并在下方补充。系统不会自动读取国际服角色。</p>}
    <label data-poe2-field>{provider === 'wegame' ? 'WeGame 公开分享链接' : 'poe.ninja 角色链接'}<input data-poe2-input aria-label="角色链接" value={url} maxLength={4096} onChange={e => setUrl(e.target.value)} placeholder={provider === 'wegame' ? 'https://www.wegame.com.cn/helper/poe2/#/share/分享标识' : 'https://poe.ninja/poe2/profile/账号/赛季/character/角色'} /></label>
    <button type="button" disabled={busy || completing || !valid || Boolean(packet && pending(packet))} onClick={() => void run(key => wowApi.poe2.createImport({provider, url: url.trim(), idempotencyKey: key}, auth), 'create:' + provider + ':' + url.trim())}>读取角色</button>
    {!valid ? <p>{url ? '链接与此入口格式不符，请检查来源和完整路径。' : '请先粘贴此来源的完整角色链接。'}</p> : null}
    {busy ? <p role="status">正在提交，请稍候…</p> : null}
    <small>{storageNotice}</small>
    {recoveryIds.map(id => <p role="alert" key={id}>上一个来源任务未能取消。<button type="button" disabled={busy || completing} onClick={() => void run(() => wowApi.poe2.getImport(id, auth), 'recover:' + id)}>恢复未取消任务</button></p>)}
    {error ? <p role="alert">{messages[error] || error}<button type="button" disabled={busy} onClick={() => packet ? void run(() => wowApi.poe2.getImport(packet.id, auth), 'read:' + packet.id) : window.location.reload()}>重新读取进度</button></p> : null}
    {packet ? <div aria-live="polite" role="status">
      <h3>{statuses[packet.status]}</h3><p>来源：{packet.provider === 'wegame' ? '国服 WeGame' : '国际服 poe.ninja'}</p>
      {packet.preview ? <dl className={styles['preview']}>{[['角色', 'character'], ['赛季', 'league'], ['等级', 'level'], ['职业', 'class'], ['升华', 'ascendancy'], ['读取时间', 'fetchedAt'], ['来源更新时间', 'sourceUpdatedAt'], ['完整性', 'completeness']].map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{display(packet.preview?.[key!])}</dd></div>)}</dl> : null}
      {packet.provider === 'ninja' || packet.preview?.['sourceRelation'] === 'user_supplied' ? <p>来源关系：用户提供（user_supplied）；尚未验证 PoB 与链接属于同一角色。</p> : null}
      {ninjaSource ? <p><a href={ninjaSource} target="_blank" rel="noopener noreferrer">打开 poe.ninja 角色页</a></p> : null}
      {Array.from(groups, ([label, issues]) => <details key={label}><summary>{label}（{issues.length} 项）</summary><ul>{issues.map((issue, i) => <li key={i}>{issue.message} · {issue.path || '角色整体'}</li>)}</ul></details>)}
      {['needs_input', 'blocked', 'failed'].includes(packet.status) || packet.nextAction === 'supply_pob' ? <div>
        <p>补充完整 PoB 2 分享码或 XML，以所提供构筑计算。请自行确认角色与配置。</p>
        <label data-poe2-field>补充 PoB 代码或 XML<textarea data-poe2-input aria-label="补充 PoB" value={source} maxLength={2000000} rows={5} onChange={e => {setSource(e.target.value); setConfirmed(false)}} /></label>
        <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />我确认使用这份构筑；系统尚未核验其与链接为同一角色。</label>
        <p><button type="button" disabled={busy || !source.trim() || !confirmed} onClick={() => void run(key => wowApi.poe2.supplyImportSource(packet.id, {source, idempotencyKey: key}, auth), 'source:' + packet.id + ':' + source)}>补充并计算基线</button></p>
        {!source.trim() || !confirmed ? <p>请粘贴完整构筑并确认来源关系后继续。</p> : null}
      </div> : null}
      {['failed', 'blocked'].includes(packet.status) ? <button type="button" disabled={busy} onClick={() => void run(key => wowApi.poe2.retryImport(packet.id, {idempotencyKey: key}, auth), 'retry:' + packet.id)}>重试导入</button> : null}
      {packet.status === 'cancelled' ? <p>已停止此任务。需要重新开始时，请填写链接并点击“读取角色”。</p> : null}
      {!['ready', 'cancelled'].includes(packet.status) ? <button type="button" disabled={busy} onClick={() => void run(() => wowApi.poe2.cancelImport(packet.id, auth), 'cancel:' + packet.id)}>取消导入</button> : null}
      {packet.status === 'ready' ? <button type="button" disabled={busy || completing} onClick={() => {delivered.current = ''; setPacket({...packet})}}>加载已完成的基线</button> : null}
    </div> : null}
  </section>
}
