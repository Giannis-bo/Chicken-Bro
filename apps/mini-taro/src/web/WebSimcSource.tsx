import { useCallback, useEffect, useRef, useState } from 'react'
import { wowApi, type ClientAuthContext, type SourceSnapshotCreateRequest } from '@wow-mini/api-client'
import type { BoundCharacter, CharacterCollection } from '@wow-mini/domain'
import type { SimcModel, SimcModelState } from '../features/simc/simc-model'
import { simcDiagnosticMessage, simcReadinessLabel, simcRequiredFieldLabel } from '../features/simc/simc-messages'
import { simcLabel } from './simc-presentation'
import styles from './WebSimc.module.scss'

type Props = { auth: Extract<ClientAuthContext, { kind: 'web' }>; model: SimcModel; state: SimcModelState; onResolving: (value: boolean) => void }
const regions: Record<string, string> = { cn: '国服', us: '美服', eu: '欧服', tw: '台服', kr: '韩服' }

export default function WebSimcSource({ auth, model, state, onResolving }: Props) {
  const [collection, setCollection] = useState<CharacterCollection>({ items: [], selectedId: null })
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(true)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [mode, setMode] = useState<'link' | 'manual'>('link')
  const [sourceUrl, setSourceUrl] = useState('')
  const [name, setName] = useState('')
  const [realm, setRealm] = useState('')
  const [region, setRegion] = useState('cn')
  const generation = useRef(0)
  const alive = useRef(false)
  const mutationGeneration = useRef(0)
  const locked = busy || !loaded || state.phase === 'submitting'

  function invalidate() {
    generation.current += 1
    model.clearSource()
    setResolving(false)
    onResolving(false)
    setError('')
  }
  const read = useCallback(async (request: SourceSnapshotCreateRequest) => {
    const version = ++generation.current
    setResolving(true)
    onResolving(true)
    try {
      await model.resolveSource('sourceUrl' in request ? request.sourceUrl : request)
    } finally {
      if (alive.current && version === generation.current) {
        setResolving(false)
        onResolving(false)
      }
    }
  }, [model, onResolving])

  const restore = useCallback(async () => {
    const version = ++generation.current
    model.clearSource({ preserveSubmission: true })
    setLoaded(false)
    setCollection({ items: [], selectedId: null })
    setActiveId(null)
    setEditing(true)
    setBusy(false)
    setError('')
    try {
      const result = await wowApi.simc.listCharacters({ auth })
      if (!alive.current || version !== generation.current) return
      if (result.fromFallback) { setError('绑定角色读取失败，请重试'); return }
      setCollection(result.payload)
      setLoaded(true)
      const selected = result.payload.items.find(item => item.id === result.payload.selectedId)
      setActiveId(selected?.id ?? null)
      setEditing(!selected)
      if (selected) await read({ sourceUrl: selected.sourceUrl })
    } catch {
      if (alive.current && version === generation.current) setError('绑定角色读取失败，请重试')
    }
  }, [auth, model, read])

  useEffect(() => {
    alive.current = true
    void restore()
    return () => {
      alive.current = false
      generation.current += 1
      mutationGeneration.current += 1
      model.clearSource({ preserveStatus: true, preserveSubmission: true })
      onResolving(false)
    }
  }, [restore, model, onResolving])

  async function change(action: 'bind' | 'select' | 'unbind', item?: BoundCharacter) {
    if (locked) return
    const mutation = ++mutationGeneration.current
    const previousId = activeId
    if (action !== 'unbind' || item?.id === previousId) invalidate()
    const version = generation.current
    setBusy(true)
    try {
      const snapshotId = state.snapshot?.id
      const result = action === 'bind' && snapshotId
        ? await wowApi.simc.bindCharacter(snapshotId, { auth })
        : action === 'select' && item
          ? await wowApi.simc.selectCharacter(item.id, { auth })
          : item ? await wowApi.simc.unbindCharacter(item.id, { auth }) : null
      if (!alive.current || version !== generation.current) return
      if (!result || result.fromFallback) {
        setError(result?.problemCode === 'CHARACTER_LIMIT_REACHED' ? '最多绑定 3 个角色，请先解绑一个角色' : '角色保存失败，请重试')
        return
      }
      setCollection(result.payload)
      // Removing another shortcut must not replace a temporary character being edited.
      if (action === 'unbind' && item?.id !== previousId) return
      const selected = result.payload.items.find(entry => entry.id === result.payload.selectedId)
      setActiveId(selected?.id ?? null)
      setEditing(!selected)
      if (selected) await read({ sourceUrl: selected.sourceUrl })
    } catch {
      if (alive.current && version === generation.current) setError('角色保存失败，请重试')
    } finally {
      if (alive.current && mutation === mutationGeneration.current) setBusy(false)
    }
  }

  const snapshot = state.snapshot
  const actor = snapshot?.character
  const ready = snapshot?.readiness === 'READY_FOR_SIMC'
  const canBind = loaded && !activeId && snapshot && actor && ['READY_FOR_SIMC', 'INCOMPLETE_FOR_SIMC'].includes(snapshot.readiness)
  const active = collection.items.find(item => item.id === activeId)
  const edited = () => { invalidate(); setActiveId(null) }

  return <section className={styles['card']}>
    <div className={styles['sectionHeading']}><h3><span className={styles['step']}>01</span>角色来源</h3><span className={styles['boundCount']} data-binding-count="">已绑定 {collection.items.length}/3</span></div>
    {collection.items.length > 0 ? <div className={styles['boundCharacters']} aria-label="已绑定角色">
      {collection.items.map(item => <div key={item.id} className={styles['boundCharacter']} data-selected={item.id === activeId}>
        <button type="button" data-simc-button="" data-bound-id={item.id} aria-pressed={item.id === activeId} disabled={locked} onClick={() => void change('select', item)}>
          <strong>{item.name}</strong><small>{regions[item.region] ?? item.region} · {item.realm}</small>
          {item.id === activeId ? <span>当前角色</span> : null}
        </button>
        <button type="button" data-simc-button="" className={styles['textButton']} aria-label={`解绑 ${item.name}`} disabled={locked} onClick={() => void change('unbind', item)}>解绑</button>
      </div>)}
    </div> : null}
    {!loaded ? <p className={styles['muted']}>{error || '正在读取绑定角色…'}</p> : null}
    {error && loaded ? <p className={styles['error']} role="alert">{error}</p> : null}
    {error && !loaded ? <button data-simc-button="" className={styles['secondaryButton']} onClick={() => void restore()}>重试绑定角色</button> : null}
    {!editing && active ? <div className={styles['sourceActions']}>
      <span className={styles['muted']}>模拟将使用 {active.name}，每次提交前更新资料。</span>
      <button data-simc-button="" className={styles['secondaryButton']} disabled={locked || resolving} onClick={() => void read({ sourceUrl: active.sourceUrl })}>{resolving ? '读取中…' : '刷新资料'}</button>
      <button data-simc-button="" className={styles['textButton']} disabled={locked} onClick={() => { invalidate(); setActiveId(null); setEditing(true) }}>添加 / 临时使用角色</button>
    </div> : null}
    {editing ? <>
      <div className={styles['sourceModes']} aria-label="角色输入方式">
        {(['link', 'manual'] as const).map(value => <button key={value} data-simc-button="" aria-pressed={mode === value} disabled={locked} onClick={() => { edited(); setMode(value) }}>{value === 'link' ? '角色链接' : '手动输入'}</button>)}
      </div>
      {mode === 'link' ? <>
        <label data-simc-label="" className={styles['field']}><span>Raider.IO 角色链接</span><div className={styles['sourceRow']}>
          <input data-simc-input="" name="sourceUrl" type="url" value={sourceUrl} disabled={locked} placeholder="粘贴 HTTPS 的 Raider.IO 角色链接" onChange={event => { edited(); setSourceUrl(event.target.value) }} />
          <button data-simc-button="" className={styles['secondaryButton']} disabled={!sourceUrl.trim() || locked || resolving} onClick={() => void read({ sourceUrl: sourceUrl.trim() })}>{resolving ? '读取中…' : '读取角色'}</button>
        </div></label>
        <div className={styles['sourceExamples']} aria-label="合法链接格式示例"><div><span className={styles['exampleLabel']}>Raider.IO 链接格式参考：</span><a className={styles['exampleLink']} href="https://raider.io/cn/characters/cn/silver-hand/Giannis" target="_blank" rel="noreferrer">https://raider.io/cn/characters/cn/silver-hand/Giannis</a></div></div>
      </> : <div className={styles['manualSource']}>
        <label data-simc-label="" className={styles['field']}><span>角色名称</span><input data-simc-input="" name="characterName" value={name} maxLength={64} disabled={locked} placeholder="角色名称" onChange={event => { edited(); setName(event.target.value) }} /></label>
        <label data-simc-label="" className={styles['field']}><span>服务器</span><input data-simc-input="" name="characterRealm" value={realm} maxLength={128} disabled={locked} placeholder="如：白银之手 / silver-hand" onChange={event => { edited(); setRealm(event.target.value) }} /></label>
        <label data-simc-label="" className={styles['field']}><span>地区</span><select name="characterRegion" value={region} disabled={locked} onChange={event => { edited(); setRegion(event.target.value) }}>{Object.entries(regions).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button data-simc-button="" className={styles['secondaryButton']} disabled={!name.trim() || !realm.trim() || locked || resolving} onClick={() => void read({ character: { name: name.trim(), realm: realm.trim(), region } })}>{resolving ? '读取中…' : '读取角色'}</button>
      </div>}
      {collection.items.length >= 3 ? <p className={styles['hint']}>已绑定 3 个角色。可临时读取其他角色，或先解绑后再绑定。</p> : null}
    </> : null}
    {!snapshot && (resolving || state.phase === 'loading') ? <p className={styles['hint']} role="status">正在读取角色资料…</p> : null}
    {snapshot ? <div className={styles['snapshot']} data-readiness={snapshot.readiness}>
      <strong>{ready ? '角色已就绪' : simcReadinessLabel(snapshot.readiness, snapshot.blockers)}{actor ? ` · ${actor.name}` : ''}</strong>
      {actor?.className.toLowerCase() === 'evoker' && actor.specialization.toLowerCase() === 'augmentation' ? <p>增辉使用 SimC 默认模拟队友估算增益，不代表实际队伍表现。</p> : null}
      {actor ? <p>{simcLabel(actor.specialization)} {simcLabel(actor.className)}{actor.level == null ? '' : ` · 等级 ${actor.level}`}</p> : null}
      {!ready && snapshot.missingFields.length > 0 && !snapshot.blockers.includes('HEALER_SPEC_UNSUPPORTED') ? <p>补齐以下资料后才能模拟；不会使用猜测数据。</p> : null}
      {snapshot.missingFields.length ? <p>缺少：{snapshot.missingFields.map(simcRequiredFieldLabel).join('、')}</p> : null}
      {snapshot.blockers.map(blocker => <p key={blocker}>{simcDiagnosticMessage(blocker)}</p>)}
      {canBind && collection.items.length < 3 ? <button data-simc-button="" className={styles['textButton']} disabled={locked || resolving} onClick={() => void change('bind')}>绑定此角色</button> : null}
    </div> : null}
  </section>
}
