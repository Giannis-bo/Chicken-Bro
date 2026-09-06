import type { SimulationJobStatus } from '@wow-mini/domain'

export const simcStatuses: Record<SimulationJobStatus, string> = {
  queued: '排队中', running: '运行中', succeeded: '已完成', failed: '失败', cancelled: '已取消',
}

export const simcFightStyles = {
  Patchwerk: '站桩战斗', HecticAddCleave: '多目标顺劈', LightMovement: '少量移动', HeavyMovement: '频繁移动',
}

const labels: Record<string, string> = {
  shaman: '萨满祭司', mage: '法师', warrior: '战士', paladin: '圣骑士', hunter: '猎人', rogue: '潜行者',
  priest: '牧师', death_knight: '死亡骑士', deathknight: '死亡骑士', monk: '武僧', druid: '德鲁伊',
  demon_hunter: '恶魔猎手', demonhunter: '恶魔猎手', evoker: '唤魔师', warlock: '术士',
  elemental: '元素', enhancement: '增强', restoration: '恢复', balance: '平衡', feral: '野性', guardian: '守护',
  arcane: '奥术', fire: '火焰', frost: '冰霜', arms: '武器', fury: '狂怒', protection: '防护',
  holy: '神圣', retribution: '惩戒', discipline: '戒律', shadow: '暗影',
  beast_mastery: '野兽控制', marksmanship: '射击', survival: '生存', assassination: '奇袭', outlaw: '狂徒', subtlety: '敏锐',
  affliction: '痛苦', demonology: '恶魔学识', destruction: '毁灭', blood: '鲜血', unholy: '邪恶',
  brewmaster: '酒仙', mistweaver: '织雾', windwalker: '踏风', havoc: '浩劫', vengeance: '复仇',
  devastation: '湮灭', preservation: '恩护', augmentation: '增辉',
  intellect: '智力', strength: '力量', agility: '敏捷', stamina: '耐力', crit: '暴击', haste: '急速',
  mastery: '精通', versatility: '全能', spell_power: '法术强度', attack_power: '攻击强度',
  crit_pct: '暴击', haste_pct: '急速', mastery_pct: '精通', versatility_pct: '全能', avoidance_pct: '闪避', leech_pct: '吸血',
  crit_rating: '暴击等级', haste_rating: '急速等级', mastery_rating: '精通等级', versatility_rating: '全能等级',
  avoidance_rating: '闪避等级', leech_rating: '吸血等级', armor: '护甲', manareg_per_second: '每秒法力恢复',
  mana: '法力', energy: '能量', rage: '怒气', maelstrom: '漩涡值', runic_power: '符文能量', focus: '集中值',
  head: '头部', neck: '颈部', shoulder: '肩部', shoulders: '肩部', back: '背部', chest: '胸部', wrist: '腕部',
  wrists: '腕部', hands: '手部', waist: '腰部', legs: '腿部', feet: '脚部', finger1: '戒指 1', finger2: '戒指 2',
  trinket1: '饰品 1', trinket2: '饰品 2', main_hand: '主手', off_hand: '副手', talents: '天赋',
  gear: '装备', equipment: '装备', class: '职业', spec: '专精', race: '种族', level: '等级',
}

export function simcLabel(value: string): string { return labels[value.trim().toLowerCase().replace(/\s+/gu, '_')] ?? value }

export function simcNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '未记录' : value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

export function simcAttributeValue(name: string, value: number): string {
  return `${simcNumber(value)}${name.endsWith('_pct') ? '%' : ''}`
}

export function simcDate(value: string): string {
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date) : '时间未记录'
}
