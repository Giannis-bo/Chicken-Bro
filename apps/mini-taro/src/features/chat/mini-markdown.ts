export type MiniBlock =
  | { kind: 'paragraph' | 'heading' | 'quote' | 'code' | 'list'; content: string }
  | { kind: 'table'; headers: string[]; rows: string[][] }
export interface MiniToken { kind: 'text' | 'bold' | 'code' | 'link'; content: string; url?: string }

// A text-only Markdown subset: never interpret HTML or load remote images.
export function miniInlineTokens(content: string): MiniToken[] {
  const pattern = /(`[^`\n]+`|\*\*[^\n]+?\*\*|__[^\n]+?__|\[[^\]\n]+\]\(https?:\/\/(?:[^()\s<>]|\([^()\s<>]*\))+\))/g
  const tokens: MiniToken[] = []
  let offset = 0
  for (const match of content.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > offset) tokens.push({ kind: 'text', content: content.slice(offset, index) })
    const value = match[0]
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s<>]+)\)$/.exec(value)
    if (link) tokens.push({ kind: 'link', content: link[1] ?? '', url: link[2] ?? '' })
    else if (value.startsWith('`')) tokens.push({ kind: 'code', content: value.slice(1, -1) })
    else tokens.push({ kind: 'bold', content: value.slice(2, -2) })
    offset = index + value.length
  }
  if (offset < content.length) tokens.push({ kind: 'text', content: content.slice(offset) })
  return tokens
}

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'))
}
function divider(line: string): boolean {
  return line.includes('|') && cells(line).every((cell) => /^:?-{3,}:?$/.test(cell))
}

export function miniMarkdownBlocks(content: string): MiniBlock[] {
  const lines = content.replace(/\r\n?/g, '\n').split('\n')
  const blocks: MiniBlock[] = []
  const special = (line: string) => /^(#{1,6}\s|\s*[-*+]\s|\s*\d+[.)]\s|>\s?|```|~~~)/.test(line)
  for (let i = 0; i < lines.length;) {
    const line = lines[i] ?? ''
    if (!line.trim() || /^\s*(---+|\*\*\*+)\s*$/.test(line)) { i++; continue }
    const fence = /^(`{3,}|~{3,})/.exec(line)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !(lines[i] ?? '').startsWith(fence[1] ?? '```')) body.push(lines[i++] ?? '')
      if (i < lines.length) i++
      blocks.push({ kind: 'code', content: body.join('\n') })
      continue
    }
    if (line.includes('|') && divider(lines[i + 1] ?? '')) {
      const headers = cells(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && (lines[i] ?? '').includes('|') && (lines[i] ?? '').trim()) rows.push(cells(lines[i++] ?? ''))
      blocks.push({ kind: 'table', headers, rows })
      continue
    }
    const heading = /^#{1,6}\s+(.+)$/.exec(line)
    if (heading) { blocks.push({ kind: 'heading', content: heading[1] ?? '' }); i++; continue }
    if (line.startsWith('>')) { blocks.push({ kind: 'quote', content: line.replace(/^>\s?/, '') }); i++; continue }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) { blocks.push({ kind: 'list', content: line.replace(/^\s*[-*+]\s+/, '• ') }); i++; continue }
    const body = [line]
    i++
    while (i < lines.length && (lines[i] ?? '').trim() && !special(lines[i] ?? '') && !divider(lines[i + 1] ?? '')) body.push(lines[i++] ?? '')
    blocks.push({ kind: 'paragraph', content: body.join('\n') })
  }
  return blocks
}
