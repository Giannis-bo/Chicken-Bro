import dictionary from './poe2-terms.zh-CN.json'

export type Poe2TermKind = 'gem' | 'class' | 'ascendancy'
export const poe2TermVersion = dictionary.version
export function poe2Term(name: string, kind: Poe2TermKind): string {
  if (!name) return '未标记'
  const entry = dictionary.terms.find(term => term.kind === kind && term.en === name)
  return entry?.zhCN ?? `${name}（国服名称待核实）`
}
export function poe2GemInput(name: string): string {
  const matches = dictionary.terms.filter(term => term.kind === 'gem' && term.zhCN === name)
  if (matches.length === 1) return matches[0]!.en
  if (/[\u3400-\u9fff]/u.test(name)) throw new Error(`“${name}”国服名称待核实，请核对名称与阶级，或使用 PoB 原文名称。`)
  return name
}
export const poe2Slots: Record<string, string> = {'Weapon 1': '主手武器', 'Weapon 2': '副手装备', Helmet: '头盔', 'Body Armour': '胸甲', Gloves: '手套', Boots: '鞋子', Amulet: '项链', 'Ring 1': '戒指 1', 'Ring 2': '戒指 2', Belt: '腰带'}
const resultSlots: Record<string, string> = {...poe2Slots, 'Charm 1': '护符 1', 'Charm 2': '护符 2', 'Charm 3': '护符 3', 'Flask 1': '药剂 1', 'Flask 2': '药剂 2'}
const configLabels: Record<string, string> = {enemyIsBoss: '敌人类型', enemyLevel: '敌人等级', enemyPhysicalReduction: '敌人物理伤害减免', enemyFireResist: '敌人火焰抗性', enemyColdResist: '敌人冰冷抗性', enemyLightningResist: '敌人闪电抗性', enemyChaosResist: '敌人混沌抗性', conditionEnemyShocked: '敌人已感电', conditionEnemyChilled: '敌人已冰缓', conditionEnemyIgnited: '敌人已点燃', conditionFullLife: '满生命', conditionLowLife: '低生命', conditionStationary: '静止状态', usePowerCharges: '使用暴击球', useFrenzyCharges: '使用狂怒球', useEnduranceCharges: '使用耐力球'}
export function poe2Config(config: Record<string, unknown>): string[] {
  const values: Record<string, string> = {None: '普通敌人', Boss: '首领', Pinnacle: '巅峰首领'}
  return Object.entries(config).filter(([key]) => key in configLabels).map(([key, value]) => `${configLabels[key]}：${typeof value === 'boolean' ? (value ? '是' : '否') : key === 'enemyIsBoss' ? values[String(value)] ?? String(value) : String(value)}`)
}
export function poe2Unsupported(line: string): string {
  if (line === 'Your unreserved Spirit is negative') return '可用精魂为负，请检查精魂保留与技能启用设置。'
  const groups = /^You have too many gem groups allocated\. Max allowed is (\d+)\. You have (\d+) non-item\/non-granted gem groups allocated\.$/u.exec(line)
  if (groups) return `技能组超过上限：最多 ${groups[1]} 组，当前启用了 ${groups[2]} 组（不含装备或额外授予的技能组）。`
  if (line === 'Passive points exceed level budget (all quest rewards assumed)') return '天赋点超过当前等级预算（已假定领取全部任务奖励）。'
  if (line.startsWith('Unrecognized gem: ')) return line.slice(18) ? `引擎未识别技能：${poe2Term(line.slice(18), 'gem')}` : '存在未识别的空技能项，请在 PoB 中核对。'
  const separator = line.indexOf(': ')
  const slot = line.slice(0, separator)
  const detail = line.slice(separator + 2)
  const effects: Record<string, string> = {'Used when you become Frozen': '被冰冻时使用', 'Used when you become Stunned': '被眩晕时使用', 'Used when you start Bleeding': '开始流血时使用', 'This Flask cannot be Used but applies its Effect constantly': '无法使用，但效果持续生效'}
  const life = /^Recover (\d+) Life when Used$/u.exec(detail)
  if (separator >= 0 && resultSlots[slot]) return `${resultSlots[slot]}：${effects[detail] ?? (life ? `使用时回复 ${life[1]} 点生命` : '词缀待核对，原文见下方原始技术数据')}（引擎未完整支持）`
  return '引擎提示待核对，原文见下方原始技术数据。'
}
