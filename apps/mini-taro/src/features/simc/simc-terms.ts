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
  intellect: '智力', strength: '力量', agility: '敏捷', stamina: '耐力', crit: '爆击', haste: '急速',
  mastery: '精通', versatility: '全能', spell_power: '法术强度', attack_power: '攻击强度',
  crit_pct: '爆击', haste_pct: '急速', mastery_pct: '精通', versatility_pct: '全能', avoidance_pct: '闪避', leech_pct: '吸血',
  crit_rating: '爆击等级', haste_rating: '急速等级', mastery_rating: '精通等级', versatility_rating: '全能等级',
  avoidance_rating: '闪避等级', leech_rating: '吸血等级', speed_rating: '加速等级', armor: '护甲', manareg_per_second: '每秒法力恢复',
  mana: '法力', energy: '能量', rage: '怒气', maelstrom: '漩涡值', runic_power: '符文能量', focus: '集中值',
  runes: '符文', combo_points: '连击点数', chi: '真气', holy_power: '圣能', soul_shard: '灵魂碎片', soul_shards: '灵魂碎片',
  astral_power: '星界能量', lunar_power: '星界能量', insanity: '狂乱值', fury_resource: '恶魔之怒', pain: '痛苦值', essence: '精华', health: '生命值',
  head: '头部', neck: '颈部', shoulder: '肩部', shoulders: '肩部', back: '背部', chest: '胸部', wrist: '腕部',
  wrists: '腕部', hands: '手部', waist: '腰部', legs: '腿部', feet: '脚部', finger1: '戒指 1', finger2: '戒指 2',
  trinket1: '饰品 1', trinket2: '饰品 2', main_hand: '主手', off_hand: '副手', talents: '天赋',
  gear: '装备', equipment: '装备', class: '职业', spec: '专精', race: '种族', level: '等级',
}

const chinese = /^[^A-Za-z]*[\u3400-\u9fff][^A-Za-z]*$/u
const termKey = (value: string) => value.trim().toLowerCase().replace(/\s+/gu, '_')

function lookup(source: Record<string, string>, key: string): string | undefined {
  return Object.hasOwn(source, key) ? source[key] : undefined
}

export function simcResourceName(value: string): string {
  return termKey(value) === 'fury' ? '恶魔之怒' : simcLabel(value)
}

export function simcLabel(value: string): string {
  return lookup(labels, termKey(value)) ?? (chinese.test(value) ? value : '名称待收录')
}

export function simcMetricName(value: string): string { return value === 'hps' ? '每秒治疗量' : '每秒伤害' }

// Matched to managed engine spell IDs and the game database's zhCN names.
// Provenance: artifacts/releases/2026-09-06-simc-workbench/zh-cn-terms.json
const spellNames: Record<string, string> = {
  "arc_discharge": "弧形放电",
  "arcanoweave_insight": "奥纹洞察",
  "ascendance": "升腾",
  "blood_fury": "血性狂怒",
  "converging_storms": "汇聚风暴",
  "crackling_surge": "爆裂涌动",
  "crash_lightning": "毁灭闪电",
  "critical_ritual": "爆击仪式",
  "devoured_strength": "噬灭之力",
  "doom_winds": "毁灭之风",
  "echoing_roar": "回响咆哮",
  "flurry": "乱舞",
  "hasty_ritual": "仓促仪式",
  "lightning_strikes": "闪电打击",
  "maelstrom_weapon": "漩涡武器",
  "masterful_ritual": "精通仪式",
  "potion_of_recklessness": "鲁莽药水",
  "short_circuit": "电涌熔断",
  "static_accumulation": "静电积聚",
  "storm_unleashed": "风暴释放",
  "stormblast": "风暴轰击",
  "stormsurge": "风暴喷涌",
  "tempest": "狂风怒号",
  "unlimited_power": "无穷力量",
  "venomcursed_mastery": "毒咒精通",
  "versatile_ritual": "全能仪式",
  "voracious_heart_of_ulatek": "乌拉特克贪婪之心",
  "xathuuxs_last_roar": "萨祖克斯的最后咆哮",
  "arcane_intellect": "奥术智慧",
  "battle_shout": "战斗怒吼",
  "blessing_of_the_bronze": "青铜龙的祝福",
  "flask_of_the_blood_knights": "血骑士合剂",
  "lightning_shield": "闪电之盾",
  "mark_of_the_wild": "野性印记",
  "power_word_fortitude": "真言术：韧",
  "skyfury": "天怒",
  "voidtouched": "虚触",
  "well_fed": "进食充分",
  "windfury_weapon": "风怒武器",
  "thorims_invocation": "托里姆的祈咒",
  "fire_nova": "火焰新星",
  "ride_the_lightning": "驾驭雷电",
  "windstrike": "风切",
  "stormstrike": "风暴打击",
  "lightning_bolt": "闪电箭",
  "windfury_attack": "风怒攻击",
  "voltaic_blaze": "流电炽焰",
  "lightning_rod": "引雷针",
  "flametongue_attack": "火舌攻击",
  "windlash": "狂风鞭笞",
  "devour_morsel": "吞噬残块",
  "flame_shock": "烈焰震击",
  "lava_lash": "熔岩猛击",
  "venomfang": "毒牙",
  "chain_lightning": "闪电链",
  "doom_winds_damage": "毁灭之风",
  "windlash_offhand": "副手狂风鞭笞",
  "bloodlust": "嗜血",
  "main_hand": "主手自动攻击",
  "offhand": "副手自动攻击",
  "melee": "自动攻击",
  "lightning_wolf:_melee": "幽灵狼：自动攻击",
  "movement": "移动",
  "potion_of_recklessness_crit": "鲁莽药水（爆击）",
  "potion_of_recklessness_penalty_vers": "鲁莽药水（全能降低）"
}

export function simcSpellName(value: string, kind: '技能' | '增益', index: number): string {
  return lookup(spellNames, termKey(value)) ?? (chinese.test(value) ? value : `名称待收录的${kind}（${index + 1}）`)
}

