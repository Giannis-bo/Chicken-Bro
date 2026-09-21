import {nodeIsAllocated, type Poe2TreeNode, type Poe2TreeEdge} from '@wow-mini/domain'

export interface TreeViewport {x: number; y: number; scale: number}
export interface TreeArt {image: HTMLImageElement; icons: Record<string, {x: number; y: number; width: number; height: number}>}
export const nodeRadius = (node: Poe2TreeNode, scale: number): number => Math.max(node.ascendancy ? node.type === 'Normal' ? 10 : 17 : node.type === 'Normal' ? 2 : 3, node.size * scale / 2)
export function fitTree(nodes: Poe2TreeNode[], width: number, height: number): TreeViewport {
  if (!nodes.length) return {x: width / 2, y: height / 2, scale: .1}
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  const scale = Math.min(1.5, (width - 90) / Math.max(200, maxX - minX), (height - 90) / Math.max(200, maxY - minY))
  return {scale: Math.max(.005, scale), x: width / 2 - (minX + maxX) / 2 * scale, y: height / 2 - (minY + maxY) / 2 * scale}
}
export function zoomAt(view: TreeViewport, factor: number, x: number, y: number): TreeViewport {
  const scale = Math.max(.005, Math.min(3, view.scale * factor))
  return {scale, x: x - (x - view.x) * scale / view.scale, y: y - (y - view.y) * scale / view.scale}
}
export function hitNode(nodes: Poe2TreeNode[], view: TreeViewport, x: number, y: number): Poe2TreeNode | undefined {
  let closest: Poe2TreeNode | undefined, distance = Infinity
  for (const node of nodes) {
    const d = Math.hypot(node.x * view.scale + view.x - x, node.y * view.scale + view.y - y)
    if (d < Math.max(9, nodeRadius(node, view.scale) + 4) && d < distance) {closest = node; distance = d}
  }
  return closest
}
export function drawTree(canvas: HTMLCanvasElement, nodes: Poe2TreeNode[], edges: Poe2TreeEdge[], view: TreeViewport,
  weapon: number, selected: number | undefined, matches: Set<number>, art: TreeArt | null) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const rect = canvas.getBoundingClientRect(), ratio = Math.min(window.devicePixelRatio || 1, 2)
  const width = rect.width || 800, height = rect.height || 520
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio)
  ctx.scale(ratio, ratio); ctx.fillStyle = '#111c1b'; ctx.fillRect(0, 0, width, height)
  const gradient = ctx.createRadialGradient(width * .5, height * .5, 0, width * .5, height * .5, width * .65)
  gradient.addColorStop(0, '#20312b'); gradient.addColorStop(1, '#0e1718'); ctx.fillStyle = gradient; ctx.fillRect(0, 0, width, height)
  const byId = new Map(nodes.map(n => [n.id, n]))
  for (const edge of edges) {
    const a = byId.get(edge.from), b = byId.get(edge.to)
    if (!a || !b) continue
    const active = nodeIsAllocated(a, weapon) && nodeIsAllocated(b, weapon)
    ctx.strokeStyle = active ? '#d5b673' : '#45534a'; ctx.lineWidth = active ? 2.4 : 1
    ctx.beginPath()
    if (edge.arc) {
      const arc = edge.arc
      ctx.arc(arc.x * view.scale + view.x, arc.y * view.scale + view.y, arc.radius * view.scale, arc.start, arc.start + arc.sweep, arc.sweep < 0)
    } else {
      ctx.moveTo(a.x * view.scale + view.x, a.y * view.scale + view.y); ctx.lineTo(b.x * view.scale + view.x, b.y * view.scale + view.y)
    }
    ctx.stroke()
  }
  for (const node of nodes) {
    const x = node.x * view.scale + view.x, y = node.y * view.scale + view.y
    const radius = nodeRadius(node, view.scale)
    if (x + radius < 0 || y + radius < 0 || x - radius > width || y - radius > height) continue
    const active = nodeIsAllocated(node, weapon), focused = node.id === selected, match = matches.has(node.id)
    ctx.beginPath(); ctx.arc(x, y, radius, 0, 2 * Math.PI)
    ctx.fillStyle = active ? '#c5a467' : '#1e2a28'; ctx.fill()
    const sprite = art?.icons[node.icon]
    if (art && sprite && radius >= 5) {
      ctx.save(); ctx.clip(); ctx.globalAlpha = active ? 1 : .52
      ctx.drawImage(art.image, sprite.x, sprite.y, sprite.width, sprite.height, x - radius, y - radius, radius * 2, radius * 2); ctx.restore()
    }
    ctx.strokeStyle = active ? '#f3d994' : node.type === 'Keystone' ? '#9988a8' : '#68756a'
    ctx.lineWidth = active ? 1.8 : 1; ctx.stroke()
    if (focused || match) {
      ctx.beginPath(); ctx.arc(x, y, radius + 5, 0, Math.PI * 2); ctx.strokeStyle = focused ? '#ffffff' : '#80daca'; ctx.lineWidth = 2; ctx.stroke()
    }
    if (active && node.allocation > 0 && radius >= 5) {
      ctx.fillStyle = node.allocation === 1 ? '#8ccff6' : '#e9a8c9'; ctx.beginPath(); ctx.arc(x + radius, y - radius, 3, 0, Math.PI * 2); ctx.fill()
    }
    if (node.type === 'ClassStart' && view.scale > .025 || focused) {
      ctx.font = '12px system-ui'; ctx.textAlign = 'center'; ctx.fillStyle = '#eee4cc'; ctx.fillText(node.name, x, y + radius + 19)
    }
  }
}
