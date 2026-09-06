export interface SimulationCharacter {
  name: string
  className: string
  specialization: string
  level: number | null
  race: string
}

export interface SimulationScenario {
  fightStyle?: string
  desiredTargets?: number
  iterations?: number
  maxTime?: number
  varyCombatLength?: number
  targetError?: number
  raidBuffs?: boolean
  bloodlust?: boolean
  gemOverrides?: Readonly<Record<string, readonly number[]>>
}

export interface SimulationRuntimeView {
  status: 'available' | 'unavailable'
  version: string | null
  gameVersion: string | null
  build: string | null
  sourceCommit: string | null
  runtimeRevision: string | null
}

export interface SimulationReport {
  schemaVersion: 1
  engine: { version: string | null; gameVersion: string | null; build: string | null }
  actor: SimulationCharacter & { talents: string | null }
  metric: { name: 'dps' | 'hps'; value: number; error: number | null }
  statistics: { iterations: number | null; fightLengthSeconds: number | null; elapsedSeconds: number | null }
  abilities: readonly { name: string; amount: number; portion: number | null; executions: number | null; critPercent: number | null }[]
  buffs: readonly { name: string; uptime: number }[]
  resources: readonly { name: string; gained: number | null; lost: number | null }[]
  attributes: readonly { name: string; value: number }[]
  gear: readonly { slot: string; itemId: number; itemLevel: number | null }[]
}

type Obj = Record<string, unknown>
function obj(v: unknown): v is Obj { return typeof v === 'object' && v !== null && !Array.isArray(v) }
function keys(v: Obj, names: string[]): boolean { return Object.keys(v).length === names.length && names.every(k => k in v) }
function str(v: unknown, max = 160): v is string { return typeof v === 'string' && v.length <= max }
function num(v: unknown, max = 1e18): v is number { return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max }
function maybe(v: unknown, check: (x: unknown) => boolean): boolean { return v === null || check(v) }
function list(v: unknown, max: number, check: (x: unknown) => boolean): boolean { return Array.isArray(v) && v.length <= max && v.every(check) }
export function isSimulationCharacter(v: unknown): v is SimulationCharacter {
  return obj(v) && keys(v, ['name', 'className', 'specialization', 'level', 'race'])
    && str(v['name']) && str(v['className']) && str(v['specialization']) && str(v['race'])
    && maybe(v['level'], n => num(n, 1000) && Number.isInteger(n))
}
export function isSimulationScenario(v: unknown): v is SimulationScenario {
  if (!obj(v) || Object.keys(v).some(k => !['fightStyle', 'desiredTargets', 'iterations', 'maxTime', 'varyCombatLength', 'targetError', 'raidBuffs', 'bloodlust', 'gemOverrides'].includes(k))) return false
  if ('fightStyle' in v && !['Patchwerk', 'HecticAddCleave', 'LightMovement', 'HeavyMovement'].includes(String(v['fightStyle']))) return false
  for (const [key, min, max] of [['desiredTargets', 1, 20], ['iterations', 1, 10000], ['maxTime', 30, 600]] as const) {
    if (key in v && !(num(v[key], max) && Number.isInteger(v[key]) && v[key] >= min)) return false
  }
  for (const [key, max] of [['varyCombatLength', .5], ['targetError', 5]] as const) if (key in v && !num(v[key], max)) return false
  for (const key of ['raidBuffs', 'bloodlust']) if (key in v && typeof v[key] !== 'boolean') return false
  if ('gemOverrides' in v) {
    const gems = v['gemOverrides']
    const slots = ['head','neck','shoulder','back','chest','wrist','hands','waist','legs','feet','finger1','finger2','trinket1','trinket2','main_hand','off_hand']
    if (!obj(gems) || Object.keys(gems).some(k => !slots.includes(k)) || !Object.values(gems).every(g => Array.isArray(g) && g.length > 0 && list(g, 32, n => num(n, 2147483647) && Number.isInteger(n) && n > 0))) return false
  }
  return true
}
export function isSimulationRuntimeView(v: unknown): v is SimulationRuntimeView {
  return obj(v) && keys(v, ['status','version','gameVersion','build','sourceCommit','runtimeRevision'])
    && (v['status'] === 'available' || v['status'] === 'unavailable')
    && ['version','gameVersion','build','runtimeRevision'].every(k => maybe(v[k], x => str(x)))
    && maybe(v['sourceCommit'], x => typeof x === 'string' && /^[0-9a-f]{40}$/u.test(x))
    && (v['status'] !== 'available' || (typeof v['version'] === 'string' && v['version'].length > 0 && typeof v['runtimeRevision'] === 'string' && v['runtimeRevision'].length > 0))
}
export function isSimulationReport(v: unknown): v is SimulationReport {
  if (!obj(v) || !keys(v, ['schemaVersion','engine','actor','metric','statistics','abilities','buffs','resources','attributes','gear']) || v['schemaVersion'] !== 1) return false
  const engine = v['engine'], actor = v['actor'], metric = v['metric'], stats = v['statistics']
  if (!obj(engine) || !keys(engine, ['version','gameVersion','build']) || !Object.values(engine).every(x => maybe(x, n => str(n)))) return false
  if (!obj(actor) || !keys(actor, ['name','className','specialization','level','race','talents']) || !maybe(actor['talents'], x => str(x, 4096))) return false
  const character = { name: actor['name'], className: actor['className'], specialization: actor['specialization'], level: actor['level'], race: actor['race'] }
  if (!isSimulationCharacter(character)) return false
  if (!obj(metric) || !keys(metric,['name','value','error']) || !['dps','hps'].includes(String(metric['name'])) || !num(metric['value']) || metric['value'] <= 0 || !maybe(metric['error'], n => num(n))) return false
  if (!obj(stats) || !keys(stats,['iterations','fightLengthSeconds','elapsedSeconds']) || !Object.values(stats).every(n => maybe(n, x => num(x)))) return false
  return list(v['abilities'], 256, a => obj(a) && keys(a,['name','amount','portion','executions','critPercent']) && str(a['name']) && num(a['amount']) && maybe(a['portion'], n => num(n,100)) && maybe(a['executions'], n => num(n)) && maybe(a['critPercent'], n => num(n,100)))
    && list(v['buffs'], 256, b => obj(b) && keys(b,['name','uptime']) && str(b['name']) && num(b['uptime'],100))
    && list(v['resources'], 32, r => obj(r) && keys(r,['name','gained','lost']) && str(r['name']) && maybe(r['gained'], n => num(n)) && maybe(r['lost'], n => num(n)))
    && list(v['attributes'], 64, a => obj(a) && keys(a,['name','value']) && str(a['name']) && num(a['value']))
    && list(v['gear'], 32, g => obj(g) && keys(g,['slot','itemId','itemLevel']) && str(g['slot']) && num(g['itemId'],2147483647) && Number.isInteger(g['itemId']) && g['itemId'] > 0 && maybe(g['itemLevel'], n => num(n,10000)))
}
