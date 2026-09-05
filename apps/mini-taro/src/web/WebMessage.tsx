import { createElement, useState, type ReactNode } from 'react'
import styles from './WebMessage.module.scss'

// Render the chat Markdown subset as React nodes. Raw HTML is always text;
// links accept HTTP(S) only, and remote images are not loaded automatically.
function inline(text: string, depth = 0): ReactNode {
  if (depth > 8) return text
  const tokens = /(`[^`\n]+`|\*\*[^\n]+?\*\*|__[^\n]+?__|~~[^\n]+?~~|\*[^*\n]+\*|\[[^\]\n]+\]\(https?:\/\/(?:[^()\s<>]|\([^()\s<>]*\))+\))/g
  const nodes: ReactNode[] = []
  let offset = 0
  for (const match of text.matchAll(tokens)) {
    const index = match.index ?? 0
    nodes.push(text.slice(offset, index))
    const token = match[0]
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s<>]+)\)$/.exec(token)
    const key = `${index}`
    if (link) {
      nodes.push(<a key={key} href={link[2]} target="_blank" rel="noopener noreferrer">{inline(link[1] ?? '', depth + 1)}</a>)
    } else if (token.startsWith('`')) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>)
    } else {
      const double = token.startsWith('**') || token.startsWith('__') || token.startsWith('~~')
      const tag = token.startsWith('~~') ? 'del' : double ? 'strong' : 'em'
      nodes.push(createElement(tag, { key }, inline(token.slice(double ? 2 : 1, double ? -2 : -1), depth + 1)))
    }
    offset = index + token.length
  }
  nodes.push(text.slice(offset))
  return nodes
}

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'))
}

function tableDivider(line: string): boolean {
  return line.includes('|') && cells(line).every((cell) => /^:?-{3,}:?$/.test(cell))
}

function blocks(content: string): ReactNode[] {
  const lines = content.replace(/\r\n?/g, '\n').split('\n')
  const nodes: ReactNode[] = []
  const special = (line: string) => /^(#{1,6}\s|\s*[-*+]\s|\s*\d+[.)]\s|>\s?|```|~~~|\s*(?:---+|\*\*\*+)\s*$)/.test(line)
  for (let i = 0; i < lines.length;) {
    const line = lines[i] ?? ''
    const key = i
    if (!line.trim()) { i++; continue }
    const fence = /^(`{3,}|~{3,})(.*)$/.exec(line)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !(lines[i] ?? '').startsWith(fence[1] ?? '```')) body.push(lines[i++] ?? '')
      if (i < lines.length) i++
      nodes.push(<pre key={key}><code>{body.join('\n')}</code></pre>)
      continue
    }
    if (line.includes('|') && tableDivider(lines[i + 1] ?? '')) {
      const header = cells(line)
      const align = cells(lines[i + 1] ?? '').map((cell) => cell.endsWith(':') ? cell.startsWith(':') ? 'center' : 'right' : 'left')
      const rows: string[][] = []
      i += 2
      while (i < lines.length && (lines[i] ?? '').includes('|') && (lines[i] ?? '').trim()) rows.push(cells(lines[i++] ?? ''))
      nodes.push(<div key={key} className={styles['tableScroll']}><table>
        <thead><tr>{header.map((cell, c) => <th key={c} style={{ textAlign: align[c] }}>{inline(cell)}</th>)}</tr></thead>
        <tbody>{rows.map((row, r) => <tr key={r}>{header.map((_, c) => <td key={c} style={{ textAlign: align[c] }}>{inline(row[c] ?? '')}</td>)}</tr>)}</tbody>
      </table></div>)
      continue
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line)
    if (heading) { nodes.push(createElement(`h${heading[1]?.length ?? 2}`, { key }, inline(heading[2] ?? ''))); i++; continue }
    if (/^\s*(?:---+|\*\*\*+)\s*$/.test(line)) { nodes.push(<hr key={key} />); i++; continue }
    const list = /^\s*([-*+]|\d+[.)])\s+(.+)$/.exec(line)
    if (list) {
      const ordered = /^\d/.test(list[1] ?? '')
      const items: ReactNode[] = []
      while (i < lines.length) {
        const item = /^\s*([-*+]|\d+[.)])\s+(.+)$/.exec(lines[i] ?? '')
        if (!item || /^\d/.test(item[1] ?? '') !== ordered) break
        let body = item[2] ?? ''
        i++
        while (i < lines.length && (lines[i] ?? '').trim() && !special(lines[i] ?? '')) body += '\n' + (lines[i++] ?? '')
        items.push(<li key={i}>{inline(body)}</li>)
      }
      nodes.push(ordered ? <ol key={key} start={parseInt(list[1] ?? '1', 10)}>{items}</ol> : <ul key={key}>{items}</ul>)
      continue
    }
    if (line.startsWith('>')) {
      const quote: string[] = []
      while (i < lines.length && (lines[i] ?? '').startsWith('>')) quote.push((lines[i++] ?? '').replace(/^>\s?/, ''))
      nodes.push(<blockquote key={key}>{inline(quote.join('\n'))}</blockquote>)
      continue
    }
    const paragraph = [line]
    i++
    while (i < lines.length && (lines[i] ?? '').trim() && !special(lines[i] ?? '') && !tableDivider(lines[i + 1] ?? '')) paragraph.push(lines[i++] ?? '')
    nodes.push(<p key={key}>{inline(paragraph.join('\n'))}</p>)
  }
  return nodes
}

export default function WebMessage({ content, markdown = false, streaming = false }: {
  content: string; markdown?: boolean; streaming?: boolean
}) {
  const [copyState, setCopyState] = useState('复制')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopyState('已复制')
    } catch { setCopyState('请选择文字复制') }
  }
  return <div className={styles['message']}>
    <div className={markdown ? styles['markdown'] : styles['plain']}>{markdown ? blocks(content) : content}</div>
    {!streaming && <button type="button" className={styles['copy']} onClick={() => void copy()} aria-label="复制消息原文">{copyState}</button>}
    <span className={styles['announcement']} role="status">{copyState === '复制' ? '' : copyState}</span>
  </div>
}
