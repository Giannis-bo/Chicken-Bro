import {useEffect, useMemo, useRef, useState} from 'react'
import {wowApi, type ClientAuthContext} from '@wow-mini/api-client'
import {nodeIsAllocated, treeNodesForView, poe2Term, type Poe2Tree, type Poe2TreeNode} from '@wow-mini/domain'
import {drawTree, fitTree, hitNode, zoomAt, type TreeViewport, type TreeArt} from './poe2-tree-canvas'
import styles from './Poe2PassiveTree.module.scss'

type Props = {auth: Extract<ClientAuthContext, {kind: 'web'}>; buildId: string; jobId?: string}
const typeNames: Record<string, string> = {Normal: '小型天赋', Notable: '核心天赋', Keystone: '基石天赋', Socket: '珠宝槽', ClassStart: '职业起点', AscendClassStart: '升华起点', Mastery: '专精'}
const treeErrors: Record<string, string> = {POE2_TREE_VERSION_MISMATCH: '此构筑的 PoB 版本与当前引擎不一致，暂时无法准确展示。', POE2_ENGINE_BUSY: '云端正在计算其他构筑，请稍后重试。', POE2_ENGINE_TIMEOUT: '读取天赋树超时，请重试。', AUTH_REQUIRED: '登录已失效，请重新登录。'}
export default function Poe2PassiveTree({auth, buildId, jobId}: Props) {
  const [loaded, setLoaded] = useState<{key: string; auth: Props['auth']; tree: Poe2Tree} | null>(null)
  const [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const key = `${buildId}:${jobId ?? ''}`
  const tree = loaded?.key === key && loaded.auth === auth ? loaded.tree : null
  useEffect(() => {
    let live = true
    setLoaded(null); setError('')
    void wowApi.poe2.getTree(buildId, auth, jobId).then(result => {
      if (!live) return
      if (result.fromFallback || !result.payload) throw new Error(result.problemCode || 'POE2_TREE_UNAVAILABLE')
      if (result.payload.buildId !== buildId || (result.payload.jobId ?? undefined) !== jobId) throw new Error('POE2_TREE_UNAVAILABLE')
      setLoaded({key, auth, tree: result.payload})
    }).catch(e => {if (live) setError(e instanceof Error ? e.message : 'POE2_TREE_UNAVAILABLE')})
    return () => {live = false}
  }, [auth, buildId, jobId, key, retry])
  if (!tree) return <section className={styles['panel']} aria-label="构筑天赋树"><div className={styles['status']} role="status">
    {error ? <>{treeErrors[error] ?? '天赋树加载失败，请重试。'} <button type="button" onClick={() => setRetry(n => n + 1)}>重试加载</button></> : '正在读取 PoB 天赋树与升华…'}
  </div></section>
  return <TreeScene key={key} tree={tree} />
}

function TreeScene({tree}: {tree: Poe2Tree}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const searchInput = useRef<HTMLInputElement>(null)
  const [ascendancy, setAscendancy] = useState(''), [weapon, setWeapon] = useState(0)
  const [query, setQuery] = useState(''), [selected, setSelected] = useState<Poe2TreeNode>()
  const [hovered, setHovered] = useState<Poe2TreeNode>()
  const [view, setView] = useState<TreeViewport>({x: 0, y: 0, scale: .1})
  const [size, setSize] = useState({width: 800, height: 550})
  const [art, setArt] = useState<TreeArt | null>(null)
  const [artFailed, setArtFailed] = useState(false)
  const pointers = useRef(new Map<number, {x: number; y: number}>())
  const gesture = useRef({moved: false, startX: 0, startY: 0})
  const nodes = useMemo(() => treeNodesForView(tree, ascendancy), [tree, ascendancy])
  const allocated = useMemo(() => nodes.filter(n => nodeIsAllocated(n, weapon)), [nodes, weapon])
  const results = useMemo(() => query.trim() ? tree.nodes.filter(n => `${n.name} ${n.id} ${n.stats.join(' ')}`.toLowerCase().includes(query.trim().toLowerCase())) : allocated, [query, tree, allocated])
  const matches = useMemo(() => new Set(query.trim() ? results.map(n => n.id) : []), [query, results])
  const ascendancies = [...new Set([tree.ascendancy, tree.secondaryAscendancy].filter(s => s && s !== 'None'))]
  const focus = (node: Poe2TreeNode) => {
    setAscendancy(node.ascendancy); setSelected(node)
    setView(node.ascendancy ? fitTree(treeNodesForView(tree, node.ascendancy), size.width, size.height)
      : {scale: .7, x: size.width / 2 - node.x * .7, y: size.height / 2 - node.y * .7})
  }
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const measure = () => {const rect = element.getBoundingClientRect(); if (rect.width) setSize({width: rect.width, height: rect.height})}
    measure()
    const observer = new ResizeObserver(measure); observer.observe(element)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    if (selected && !ascendancy && !selected.ascendancy) setView({scale: .7, x: size.width / 2 - selected.x * .7, y: size.height / 2 - selected.y * .7})
    else setView(fitTree(ascendancy || !allocated.length ? nodes : allocated, size.width, size.height))
    // Selection uses focus(); changing the viewport must not reset itself.
  }, [ascendancy, size])
  useEffect(() => {
    if (!tree.engineVersion.includes('7d6f530c') || tree.treeVersion !== '0_5') {setArtFailed(true); return}
    let live = true
    const base = (typeof __WOW_H5_PUBLIC_PATH__ === 'string' ? __WOW_H5_PUBLIC_PATH__ : '/') + 'poe2-tree-art/7d6f530c/'
    void fetch(base + 'manifest.json').then(r => {if (!r.ok) throw new Error('art'); return r.json()}).then(manifest => {
      if (manifest.engineCommit !== '7d6f530cbdab20389ff8bc6ba97a37ac27f74e41' || manifest.treeVersion !== tree.treeVersion) throw new Error('art version')
      const img = new Image()
      img.onload = () => {if (live) setArt({image: img, icons: manifest.icons})}
      img.onerror = () => {if (live) setArtFailed(true)}
      img.src = base + 'icons.webp'
    }).catch(() => {if (live) setArtFailed(true)})
    return () => {live = false}
  }, [tree.engineVersion, tree.treeVersion])
  useEffect(() => {if (canvas.current) drawTree(canvas.current, nodes, tree.edges, view, weapon, selected?.id, matches, art)}, [nodes, tree, view, weapon, selected, matches, size, art])
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); const rect = element.getBoundingClientRect()
      setView(v => zoomAt(v, Math.exp(-Math.max(-150, Math.min(150, event.deltaY)) * .003), event.clientX - rect.left, event.clientY - rect.top))
    }
    element.addEventListener('wheel', wheel, {passive: false})
    return () => element.removeEventListener('wheel', wheel)
  }, [])
  const changeView = (value: string) => {setSelected(undefined); setHovered(undefined); setQuery(''); setAscendancy(value)}
  const fit = (all: boolean) => {setSelected(undefined); setView(fitTree(all || !allocated.length ? nodes : allocated, size.width, size.height))}
  return <section className={styles['panel']} aria-label="构筑天赋树" data-tree-nodes={tree.nodes.length} data-art-ready={Boolean(art)}>
    <header className={styles['heading']}><div><h2>天赋树与升华</h2><p>{tree.jobId ? '当前计算结果的天赋分配' : '原始构筑的天赋分配'} · 树版本 {tree.treeVersion.replace('_', '.')}</p></div><p>当前视图已点 {allocated.filter(n => !n.type.endsWith('Start')).length} 个节点</p></header>
    <div className={styles['toolbar']}>
      <button type="button" aria-pressed={!ascendancy} onClick={() => changeView('')}>天赋树</button>
      {ascendancies.map(name => <button key={name} type="button" aria-pressed={ascendancy === name} onClick={() => changeView(name)}>升华 · {poe2Term(name, 'ascendancy')}</button>)}
      {!ascendancies.length ? <span>此构筑尚未选择升华</span> : null}
      <select aria-label="天赋武器组" value={weapon} onChange={e => setWeapon(Number(e.target.value))}><option value={0}>全部分配</option><option value={1}>武器组 1</option><option value={2}>武器组 2</option></select>
      <div className={styles['searchBox']}>
        <svg className={styles['searchIcon']} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" strokeLinecap="round" /></svg>
        <input ref={searchInput} className={styles['searchInput']} aria-label="搜索天赋节点" placeholder="搜索节点名称、属性或编号" autoComplete="off" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => {if (e.key === 'Escape') setQuery('')}} />
        {query ? <button className={styles['searchClear']} type="button" aria-label="清空节点搜索" onClick={() => {setQuery(''); searchInput.current?.focus()}}>×</button> : null}
      </div>
    </div>
    <div className={styles['layout']}><div className={styles['stage']}>
      <div className={styles['legend']}>金色：已分配 · 蓝点：武器组 1 · 粉点：武器组 2<br />拖拽移动 · 滚轮或双指缩放 · 点击查看节点</div>
      {hovered ? <div className={styles['tooltip']} role="tooltip"><strong>{hovered.name}</strong>{hovered.stats.slice(0, 5).map((line, i) => <div key={i}>{line}</div>)}</div> : null}
      <canvas ref={canvas} className={styles['canvas']} tabIndex={0} aria-label="交互天赋树，方向键移动，加减键缩放；也可使用节点列表查看详情"
        onKeyDown={e => {
          if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-'].includes(e.key)) e.preventDefault()
          if (e.key === '+' || e.key === '=') setView(v => zoomAt(v, 1.3, size.width / 2, size.height / 2))
          if (e.key === '-') setView(v => zoomAt(v, 1 / 1.3, size.width / 2, size.height / 2))
          if (e.key.startsWith('Arrow')) setView(v => ({...v, x: v.x + (e.key === 'ArrowLeft' ? 50 : e.key === 'ArrowRight' ? -50 : 0), y: v.y + (e.key === 'ArrowUp' ? 50 : e.key === 'ArrowDown' ? -50 : 0)}))
        }}
        onPointerDown={e => {
          setHovered(undefined)
          e.currentTarget.setPointerCapture(e.pointerId)
          pointers.current.set(e.pointerId, {x: e.clientX, y: e.clientY})
          gesture.current = {moved: pointers.current.size > 1, startX: e.clientX, startY: e.clientY}
        }}
        onPointerMove={e => {
          const old = pointers.current.get(e.pointerId)
          if (!old) {const r = e.currentTarget.getBoundingClientRect(); setHovered(hitNode(nodes, view, e.clientX - r.left, e.clientY - r.top)); return}
          const other = [...pointers.current.entries()].find(([id]) => id !== e.pointerId)?.[1]
          pointers.current.set(e.pointerId, {x: e.clientX, y: e.clientY})
          if (Math.hypot(e.clientX - gesture.current.startX, e.clientY - gesture.current.startY) > 4) gesture.current.moved = true
          if (other) {
            gesture.current.moved = true
            const before = Math.hypot(old.x - other.x, old.y - other.y), after = Math.hypot(e.clientX - other.x, e.clientY - other.y), rect = e.currentTarget.getBoundingClientRect()
            if (before > 1) setView(v => zoomAt(v, after / before, (e.clientX + other.x) / 2 - rect.left, (e.clientY + other.y) / 2 - rect.top))
          } else setView(v => ({...v, x: v.x + e.clientX - old.x, y: v.y + e.clientY - old.y}))
        }}
        onPointerUp={e => {
          if (!gesture.current.moved) {const r = e.currentTarget.getBoundingClientRect(); setSelected(hitNode(nodes, view, e.clientX - r.left, e.clientY - r.top))}
          pointers.current.delete(e.pointerId)
        }}
        onPointerCancel={e => {pointers.current.delete(e.pointerId); gesture.current.moved = true}}
        onPointerLeave={() => setHovered(undefined)}
        onLostPointerCapture={e => pointers.current.delete(e.pointerId)} />
      <div className={styles['controls']}><button type="button" aria-label="放大天赋树" onClick={() => setView(v => zoomAt(v, 1.4, size.width / 2, size.height / 2))}>＋</button><button type="button" aria-label="缩小天赋树" onClick={() => setView(v => zoomAt(v, 1 / 1.4, size.width / 2, size.height / 2))}>−</button><button type="button" onClick={() => fit(false)}>定位已点</button><button type="button" onClick={() => fit(true)}>查看全树</button></div>
    </div><aside className={styles['detail']} aria-label="节点详情">
      <div className={styles['nodeInfo']}>{selected ? <><h3 className={styles['nodeTitle']}>{selected.name}</h3><small>{typeNames[selected.type] ?? selected.type} · #{selected.id}</small><p className={styles['nodeDescription']}>{nodeIsAllocated(selected, weapon) ? '已分配' : selected.allocated ? '已分配至另一武器组' : '未分配'}{selected.allocation ? ` · 武器组 ${selected.allocation}` : ''}</p><ul className={styles['nodeStats']}>{selected.stats.map((line, index) => <li key={index}>{line}</li>)}</ul></> : <><h3 className={styles['nodeTitle']}>探索你的构筑</h3><p className={styles['nodeDescription']}>点击节点查看属性，或从下方列表定位已点节点。</p></>}</div>
      <div className={styles['listHeading']}>{query.trim() ? `搜索结果 · ${results.length}` : `当前视图已点节点 · ${results.length}`}</div>
      <div className={styles['results']} aria-label="天赋节点列表">{results.slice(0, 150).map(node => <button className={styles['nodeRow']} type="button" key={node.id} aria-pressed={selected?.id === node.id} onClick={() => focus(node)}><span className={styles['nodeName']}>{node.name}</span><small className={styles['nodeId']}>#{node.id}</small></button>)}{!results.length ? <p>{query.trim() ? '没有匹配节点' : '此视图没有已分配节点'}</p> : null}{results.length > 150 ? <p>显示前 150 项，请细化搜索。</p> : null}</div>
    </aside></div>
    <div className={styles['footer']}>节点名称与属性使用简体中文，数值来自当前 PoB 构筑。{artFailed ? '图标暂不可用，节点布局与分配正常展示。' : ''}</div>
  </section>
}
