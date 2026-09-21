export interface Poe2TreeNode {
  id: number
  x: number
  y: number
  name: string
  stats: string[]
  type: string
  ascendancy: string
  allocated: boolean
  allocation: number
  icon: string
  size: number
}
export interface Poe2TreeEdge {
  from: number
  to: number
  arc?: {x: number; y: number; radius: number; start: number; sweep: number}
}
export interface Poe2Tree {
  buildId: string
  jobId?: string | null
  treeVersion: string
  engineVersion: string
  inputSha256: string
  className: string
  ascendancy: string
  secondaryAscendancy: string
  nodes: Poe2TreeNode[]
  edges: Poe2TreeEdge[]
}
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const integer = (v: unknown): v is number => finite(v) && Number.isInteger(v) && v >= 0
export function isPoe2Tree(v: unknown): v is Poe2Tree {
  if (!record(v) || ['userId', 'user_id', 'ownerId'].some(key => key in v)
    || !['buildId', 'treeVersion', 'engineVersion', 'inputSha256', 'className', 'ascendancy', 'secondaryAscendancy'].every(k => typeof v[k] === 'string')
    || !/^[a-f0-9]{64}$/u.test(String(v['inputSha256']))
    || !Array.isArray(v['nodes']) || !v['nodes'].length || v['nodes'].length > 20000 || !Array.isArray(v['edges']) || v['edges'].length > 50000) return false
  if (!v['nodes'].every(n => record(n) && integer(n['id']) && finite(n['x']) && finite(n['y'])
    && ['name', 'type', 'ascendancy', 'icon'].every(k => typeof n[k] === 'string')
    && Array.isArray(n['stats']) && n['stats'].every(s => typeof s === 'string')
    && typeof n['allocated'] === 'boolean' && [0, 1, 2].includes(Number(n['allocation'])) && integer(n['allocation'])
    && finite(n['size']) && n['size'] > 0)) return false
  const ids = new Set(v['nodes'].map(n => n.id as number))
  if (ids.size !== v['nodes'].length) return false
  return v['edges'].every(e => {
    if (!record(e) || !integer(e['from']) || !integer(e['to']) || !ids.has(e['from']) || !ids.has(e['to'])) return false
    if (!('arc' in e)) return true
    const arc = e['arc']
    return record(arc) && ['x', 'y', 'radius', 'start', 'sweep'].every(k => finite(arc[k])) && Number(arc['radius']) > 0
  })
}
export const treeNodesForView = (tree: Poe2Tree, ascendancy: string): Poe2TreeNode[] => tree.nodes.filter(node => node.ascendancy === ascendancy)
export const nodeIsAllocated = (node: Poe2TreeNode, weapon: number): boolean => node.allocated && (weapon === 0 || node.allocation === 0 || node.allocation === weapon)
