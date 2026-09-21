export interface SimulationPhaseState {
  resources?: Readonly<Record<string, number | 'max'>>
  buffs?: Readonly<Record<string, { stacks: number; remainingSeconds: number | 'full' }>>
  cooldowns?: Readonly<Record<string, number>>
}
export interface SimulationPhaseMeasurement {
  durationSeconds: number
  actions?: readonly { action: string; buff?: string }[]
}
export interface SimulationPhaseAssertions {
  openingActions?: readonly string[]
  requiredBuffs?: readonly string[]
  maxResourceOverflow?: Readonly<Record<string, number>>
}
type Obj = Record<string, unknown>
function obj(v: unknown): v is Obj { return typeof v === 'object' && v !== null && !Array.isArray(v) }
function token(v: unknown): v is string { return typeof v === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_]{0,79}$/.test(v) }
function num(v: unknown, min = 0, max = 1e7): v is number { return typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max }
function fields(v: Obj, allowed: string[]): boolean { return Object.keys(v).every(k => allowed.includes(k)) }
function map(v: unknown, check: (x: unknown) => boolean): boolean { return obj(v) && Object.keys(v).length <= 32 && Object.entries(v).every(([k, x]) => token(k) && check(x)) }
export function isSimulationPhase(v: Obj): boolean {
  if (!['initialState', 'measurement', 'assertions'].some(k => k in v)) return true
  const apl = v['actionLists']
  if (!obj(apl) || !Array.isArray(apl['default']) || !apl['default'].length) return false
  if ('precombat' in apl && JSON.stringify(apl['precombat']) !== '["snapshot_stats"]') return false
  if (Object.values(apl).some(rows => Array.isArray(rows) && rows.some(row => typeof row === 'string' && /^(strict_sequence|sequence)(,|$)/.test(row)))) return false
  const m = v['measurement']
  if (!obj(m) || !fields(m, ['durationSeconds', 'actions']) || !num(m['durationSeconds'], 20, 120) || !Number.isInteger(m['durationSeconds'])) return false
  if ('maxTime' in v && v['maxTime'] !== m['durationSeconds']) return false
  if ('varyCombatLength' in v && v['varyCombatLength'] !== 0 || 'targetError' in v && v['targetError'] !== 0) return false
  if ('iterations' in v && (!num(v['iterations'], 1, 128) || !Number.isInteger(v['iterations']))) return false
  if ('actions' in m && (!Array.isArray(m['actions']) || m['actions'].length > 16 || !m['actions'].every(a => obj(a) && fields(a, ['action', 'buff']) && token(a['action']) && (!('buff' in a) || token(a['buff']))))) return false
  const s = v['initialState']
  if (s !== undefined && (!obj(s) || !fields(s, ['resources', 'buffs', 'cooldowns'])
    || 'resources' in s && !map(s['resources'], x => x === 'max' || num(x))
    || 'cooldowns' in s && !map(s['cooldowns'], x => num(x, .001, 600))
    || 'buffs' in s && !map(s['buffs'], x => obj(x) && fields(x, ['stacks', 'remainingSeconds']) && num(x['stacks'], 1, 100) && Number.isInteger(x['stacks']) && (x['remainingSeconds'] === 'full' || num(x['remainingSeconds'], .001, 600))))) return false
  const a = v['assertions']
  if (a !== undefined) {
    if (!obj(a) || !fields(a, ['openingActions', 'requiredBuffs', 'maxResourceOverflow'])) return false
    for (const k of ['openingActions', 'requiredBuffs']) if (k in a && (!Array.isArray(a[k]) || a[k].length < 1 || a[k].length > 16 || !a[k].every(token))) return false
    if ('maxResourceOverflow' in a && !map(a['maxResourceOverflow'], x => num(x))) return false
  }
  return true
}
