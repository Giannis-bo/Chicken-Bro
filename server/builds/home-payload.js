const { buildCurrentSeasonPayload, seasonMetadataFields } = require('../game-season')

const queryTypes = [
  {
    key: 'talents',
    title: '天赋构筑',
    desc: '按大秘境、团本和通用场景查看高端玩家常用天赋。'
  },
  {
    key: 'gear',
    title: '装备模拟',
    desc: '替换装备、补齐 16 槽并保存装备配置字符串。'
  },
  {
    key: 'statWeights',
    title: '属性权重',
    desc: '结合日志、模拟和榜单样本给出属性收益方向。'
  },
  {
    key: 'rotation',
    title: '输出循环',
    desc: '拆解起手、爆发、平稳期和副本场景处理。'
  }
]

const firstVersionQueryKeys = new Set(['talents', 'gear'])
const firstVersionHomeActions = [
  ...queryTypes.filter((item) => firstVersionQueryKeys.has(item.key)),
  {
    key: 'simc',
    title: '模拟 SimC',
    desc: '组合已保存的天赋与装备模板，进入固定 SimC 工作台。'
  },
  {
    key: 'tasks',
    title: '任务列表',
    desc: '查看最近提交过的模拟任务，继续追踪结果。'
  }
]

const trustedBuildSources = [
  {
    name: 'Raider.IO',
    url: 'https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards',
    note: '高层大秘境队伍、角色分数、专精占比和路线样本。'
  },
  {
    name: 'Warcraft Logs',
    url: 'https://www.warcraftlogs.com/zone/rankings/latest',
    note: '团本和大秘境日志、伤害构成、技能覆盖率和排名样本。'
  },
  {
    name: 'Archon',
    url: 'https://www.archon.gg/wow',
    note: '基于 Warcraft Logs 的职业专精、天赋、装备和统计聚合。'
  },
  {
    name: 'Subcreation',
    url: 'https://www.subcreation.net/',
    note: '大秘境与团本构筑聚合、专精趋势和装备热度。'
  }
]

const classes = [
  ['死亡骑士', ['鲜血', '冰霜', '邪恶']],
  ['恶魔猎手', ['浩劫', '复仇', '噬灭']],
  ['德鲁伊', ['平衡', '野性', '守护', '恢复']],
  ['唤魔师', ['湮灭', '恩护', '增辉']],
  ['猎人', ['野兽控制', '射击', '生存']],
  ['法师', ['奥术', '火焰', '冰霜']],
  ['武僧', ['酒仙', '织雾', '踏风']],
  ['圣骑士', ['神圣', '防护', '惩戒']],
  ['牧师', ['戒律', '神圣', '暗影']],
  ['潜行者', ['刺杀', '狂徒', '敏锐']],
  ['萨满祭司', ['元素', '增强', '恢复']],
  ['术士', ['痛苦', '恶魔学识', '毁灭']],
  ['战士', ['武器', '狂怒', '防护']]
]

const roleByClassSpec = {
  '死亡骑士-鲜血': '坦克',
  '恶魔猎手-复仇': '坦克',
  '德鲁伊-守护': '坦克',
  '武僧-酒仙': '坦克',
  '圣骑士-防护': '坦克',
  '战士-防护': '坦克',
  '德鲁伊-恢复': '治疗',
  '唤魔师-恩护': '治疗',
  '武僧-织雾': '治疗',
  '圣骑士-神圣': '治疗',
  '牧师-戒律': '治疗',
  '牧师-神圣': '治疗',
  '萨满祭司-恢复': '治疗',
  '德鲁伊-平衡': '远程输出',
  '唤魔师-湮灭': '远程输出',
  '唤魔师-增辉': '辅助输出',
  '猎人-野兽控制': '远程输出',
  '猎人-射击': '远程输出',
  '法师-奥术': '远程输出',
  '法师-火焰': '远程输出',
  '法师-冰霜': '远程输出',
  '牧师-暗影': '远程输出',
  '萨满祭司-元素': '远程输出',
  '术士-痛苦': '远程输出',
  '术士-恶魔学识': '远程输出',
  '术士-毁灭': '远程输出'
}

const latestAnalysis = {
  publishedAt: '2026-06-09',
  analysisWindow: '近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本'
}

const classSlugByName = {
  '死亡骑士': 'death-knight',
  '恶魔猎手': 'demon-hunter',
  '德鲁伊': 'druid',
  '唤魔师': 'evoker',
  '猎人': 'hunter',
  '法师': 'mage',
  '武僧': 'monk',
  '圣骑士': 'paladin',
  '牧师': 'priest',
  '潜行者': 'rogue',
  '萨满祭司': 'shaman',
  '术士': 'warlock',
  '战士': 'warrior'
}

const websimClassKeyByName = {
  '死亡骑士': 'deathknight',
  '恶魔猎手': 'demonhunter',
  '德鲁伊': 'druid',
  '唤魔师': 'evoker',
  '猎人': 'hunter',
  '法师': 'mage',
  '武僧': 'monk',
  '圣骑士': 'paladin',
  '牧师': 'priest',
  '潜行者': 'rogue',
  '萨满祭司': 'shaman',
  '术士': 'warlock',
  '战士': 'warrior'
}

const specSlugByName = {
  '鲜血': 'blood',
  '冰霜': 'frost',
  '邪恶': 'unholy',
  '浩劫': 'havoc',
  '复仇': 'vengeance',
  '噬灭': 'devourer',
  '平衡': 'balance',
  '野性': 'feral',
  '守护': 'guardian',
  '恢复': 'restoration',
  '湮灭': 'devastation',
  '恩护': 'preservation',
  '增辉': 'augmentation',
  '野兽控制': 'beast-mastery',
  '射击': 'marksmanship',
  '生存': 'survival',
  '奥术': 'arcane',
  '火焰': 'fire',
  '酒仙': 'brewmaster',
  '织雾': 'mistweaver',
  '踏风': 'windwalker',
  '神圣': 'holy',
  '防护': 'protection',
  '惩戒': 'retribution',
  '戒律': 'discipline',
  '暗影': 'shadow',
  '刺杀': 'assassination',
  '狂徒': 'outlaw',
  '敏锐': 'subtlety',
  '元素': 'elemental',
  '增强': 'enhancement',
  '痛苦': 'affliction',
  '恶魔学识': 'demonology',
  '毁灭': 'destruction',
  '武器': 'arms',
  '狂怒': 'fury'
}

const websimSpecKeyByName = {
  '鲜血': 'blood',
  '冰霜': 'frost',
  '邪恶': 'unholy',
  '浩劫': 'havoc',
  '复仇': 'vengeance',
  '噬灭': 'devourer',
  '平衡': 'balance',
  '野性': 'feral',
  '守护': 'guardian',
  '恢复': 'restoration',
  '湮灭': 'devastation',
  '恩护': 'preservation',
  '增辉': 'augmentation',
  '野兽控制': 'beast_mastery',
  '射击': 'marksmanship',
  '生存': 'survival',
  '奥术': 'arcane',
  '火焰': 'fire',
  '酒仙': 'brewmaster',
  '织雾': 'mistweaver',
  '踏风': 'windwalker',
  '神圣': 'holy',
  '防护': 'protection',
  '惩戒': 'retribution',
  '戒律': 'discipline',
  '暗影': 'shadow',
  '刺杀': 'assassination',
  '狂徒': 'outlaw',
  '敏锐': 'subtlety',
  '元素': 'elemental',
  '增强': 'enhancement',
  '痛苦': 'affliction',
  '恶魔学识': 'demonology',
  '毁灭': 'destruction',
  '武器': 'arms',
  '狂怒': 'fury'
}

const wowIconBaseUrl = 'https://wow.zamimg.com/images/wow/icons/large'

const classIconNameByKey = {
  deathknight: 'classicon_deathknight',
  demonhunter: 'classicon_demonhunter',
  druid: 'classicon_druid',
  evoker: 'classicon_evoker',
  hunter: 'classicon_hunter',
  mage: 'classicon_mage',
  monk: 'classicon_monk',
  paladin: 'classicon_paladin',
  priest: 'classicon_priest',
  rogue: 'classicon_rogue',
  shaman: 'classicon_shaman',
  warlock: 'classicon_warlock',
  warrior: 'classicon_warrior'
}

const specIconNameByKey = {
  arcane: 'spell_holy_magicalsentry',
  fire: 'spell_fire_firebolt02',
  frost: 'spell_frost_frostbolt02',
  holy: 'spell_holy_holybolt',
  protection: 'ability_warrior_defensivestance',
  retribution: 'spell_holy_auraoflight',
  elemental: 'spell_nature_lightning',
  enhancement: 'spell_shaman_improvedstormstrike',
  restoration: 'spell_nature_magicimmunity',
  arms: 'ability_warrior_savageblow',
  fury: 'ability_warrior_innerrage',
  blood: 'spell_deathknight_bloodpresence',
  unholy: 'spell_deathknight_unholypresence',
  havoc: 'ability_demonhunter_specdps',
  vengeance: 'ability_demonhunter_spectank',
  devourer: 'ability_demonhunter_specdevourer',
  balance: 'spell_nature_starfall',
  feral: 'ability_druid_catform',
  guardian: 'ability_racial_bearform',
  devastation: 'classicon_evoker_devastation',
  preservation: 'classicon_evoker_preservation',
  augmentation: 'classicon_evoker_augmentation',
  beast_mastery: 'ability_hunter_bestialdiscipline',
  marksmanship: 'ability_hunter_focusedaim',
  survival: 'ability_hunter_camouflage',
  brewmaster: 'spell_monk_brewmaster_spec',
  mistweaver: 'spell_monk_mistweaver_spec',
  windwalker: 'spell_monk_windwalker_spec',
  discipline: 'spell_holy_powerwordshield',
  shadow: 'spell_shadow_shadowwordpain',
  assassination: 'ability_rogue_eviscerate',
  outlaw: 'ability_rogue_waylay',
  subtlety: 'ability_stealth',
  affliction: 'spell_shadow_deathcoil',
  demonology: 'spell_shadow_metamorphosis',
  destruction: 'spell_shadow_rainoffire'
}

function wowIconUrl(iconName) {
  const normalized = String(iconName || 'inv_misc_questionmark').toLowerCase().replace(/[^a-z0-9_]+/g, '') || 'inv_misc_questionmark'
  return `${wowIconBaseUrl}/${normalized}.jpg`
}

function gameAssetFromIconUrl(entityType, entityId, iconUrl, fallbackText, semanticTags) {
  return {
    entityType,
    entityId,
    iconUrl,
    fallbackText,
    resolutionTier: 'icon_large',
    source: 'static_icon_name',
    status: iconUrl ? 'fallback' : 'missing',
    semanticTags: semanticTags || [],
    usage: ['builds_home', 'current_spec_workbench']
  }
}

const statPriorityByRole = {
  '坦克': [
    ['Primary', '主属性', 100],
    ['Haste', '高层节奏', 88],
    ['Mastery', '承伤稳定', 76],
    ['Versatility', '全局减伤', 68],
    ['Critical Strike', '输出/招架', 58]
  ],
  '治疗': [
    ['Primary', '主属性', 100],
    ['Haste', '施法节奏', 90],
    ['Critical Strike', '爆发治疗', 82],
    ['Mastery', '专精收益', 72],
    ['Versatility', '生存/泛用', 54]
  ],
  '辅助输出': [
    ['Intellect', '主属性', 100],
    ['Critical Strike', '团队增益窗口', 96],
    ['Haste', '循环节奏', 78],
    ['Mastery', '专精联动', 56],
    ['Versatility', '泛用收益', 38]
  ],
  '远程输出': [
    ['Primary', '主属性', 100],
    ['Haste', '循环节奏', 86],
    ['Critical Strike', '爆发收益', 78],
    ['Mastery', '专精联动', 70],
    ['Versatility', '稳定收益', 48]
  ],
  '近战输出': [
    ['Primary', '主属性', 100],
    ['Critical Strike', '爆发收益', 86],
    ['Haste', '资源循环', 78],
    ['Mastery', '专精联动', 70],
    ['Versatility', '稳定收益', 50]
  ]
}

const rotationByRole = {
  '坦克': [
    ['建立仇恨', '开怪先建立主要减伤和群体仇恨，保证队伍能安全爆发。'],
    ['主动减伤', '把主动减伤覆盖在高伤害窗口，不把生存技能全部交给低压小怪。'],
    ['资源回补', '根据真实承伤使用自疗或资源支出，避免满资源溢出。'],
    ['高层工具', '打断、群控、位移和团队减伤按副本机制提前规划。']
  ],
  '治疗': [
    ['伤害前准备', '高压到来前预铺 HoT、护盾、信标或核心治疗增益。'],
    ['爆发治疗', '把大治疗技能留给可预判的群体伤害或点名机制。'],
    ['输出穿插', '安全窗口补伤害和功能技能，保持高端日志常见的治疗/输出节奏。'],
    ['工具处理', '驱散、群驱、外部减伤和控制优先服务副本机制。']
  ],
  '辅助输出': [
    ['增益铺垫', '提前确认队友爆发窗口，把核心增益给到最高价值目标。'],
    ['窗口对齐', '团队爆发、饰品和副本高价值波次对齐后再交主要技能。'],
    ['循环维持', '用填充技能延长增益或维持资源，不让核心 buff 断在关键波次。'],
    ['功能支援', '减伤、位移、控制和救援技能按队伍计划使用。']
  ],
  '远程输出': [
    ['起手爆发', '提前站位，按构筑要求完成 opener 并建立主要 DoT、宠物或资源循环。'],
    ['优先级循环', '围绕核心触发、资源上限和短 CD 技能按优先级输出。'],
    ['移动处理', '把瞬发、位移和可移动施法留给机制，减少高价值读条损失。'],
    ['大秘境波次', '爆发技能按高危波次、易伤窗口或队伍拉怪节奏安排。']
  ],
  '近战输出': [
    ['起手爆发', '开怪迅速建立资源、DoT 或主要增益，并把大技能打进队伍爆发。'],
    ['资源循环', '避免能量、怒气、连击点或符文类资源溢出。'],
    ['转火处理', '把短 CD 和高价值触发留给优先击杀目标或副本机制。'],
    ['生存工具', '高层中自保、打断、群控和位移会直接影响可用输出窗口。']
  ]
}

function slugFor(className, specName) {
  return `${className}-${specName}`.replace(/\s+/g, '-')
}

function roleFor(className, specName) {
  return roleByClassSpec[`${className}-${specName}`] || '近战输出'
}

function makeSpecialization(className, specName) {
  const role = roleFor(className, specName)
  const classKey = websimClassKeyByName[className] || ''
  const specKey = websimSpecKeyByName[specName] || ''
  const classIconUrl = wowIconUrl(classIconNameByKey[classKey])
  const specIconUrl = wowIconUrl(specIconNameByKey[specKey] || classIconNameByKey[classKey])
  return {
    id: slugFor(className, specName),
    className,
    specName,
    role,
    title: `${specName}${className}`,
    status: role,
    classSlug: classSlugByName[className] || '',
    specSlug: specSlugByName[specName] || '',
    websimClassKey: classKey,
    websimSpecKey: specKey,
    classIconUrl,
    specIconUrl,
    iconUrl: specIconUrl,
    classGameAsset: gameAssetFromIconUrl(
      'playable_class',
      classKey || className,
      classIconUrl,
      className.slice(0, 1),
      ['game', 'class', classKey].filter(Boolean)
    ),
    gameAsset: gameAssetFromIconUrl(
      'playable_spec',
      `${classKey}:${specKey}`,
      specIconUrl,
      specName.slice(0, 1),
      ['game', 'class', 'spec', classKey, specKey].filter(Boolean)
    ),
    desc: `${role}专精，详情页首版聚焦天赋构筑和装备模拟。`,
    sourceName: 'Archon',
    sourceUrl: 'https://www.archon.gg/wow',
    publishedAt: latestAnalysis.publishedAt,
    analysisWindow: latestAnalysis.analysisWindow,
    sourceNote: '由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。'
  }
}

const specializations = classes.flatMap(([className, specs]) =>
  specs.map((specName) => makeSpecialization(className, specName))
)

const classOptions = classes.map(([className, specs]) => {
  const classKey = websimClassKeyByName[className] || ''
  const iconUrl = wowIconUrl(classIconNameByKey[classKey])
  return {
    name: className,
    websimClassKey: classKey,
    iconUrl,
    gameAsset: gameAssetFromIconUrl(
      'playable_class',
      classKey || className,
      iconUrl,
      className.slice(0, 1),
      ['game', 'class', classKey].filter(Boolean)
    ),
    specializations: specs.map((specName) => makeSpecialization(className, specName))
  }
})

const featuredIds = [
  '法师-冰霜',
  '圣骑士-防护',
  '唤魔师-增辉',
  '牧师-戒律',
  '死亡骑士-鲜血'
]

const archonSnapshots = {
  '死亡骑士-鲜血': { statPriority: 'Strength > Mastery > Vers > Crit > Haste', gear: ["Relentless Rider's Crown", "Masterwork Sin'dorei Amulet", "Relentless Rider's Dreadthorns"], talentPopularity: '2.2%', maxKey: '+22' },
  '死亡骑士-冰霜': { statPriority: 'Strength > Mastery > Crit > Haste > Vers', gear: ["Relentless Rider's Crown", "Masterwork Sin'dorei Amulet", 'Shoulderplates of Frozen Blood'], talentPopularity: '6.2%', maxKey: '+22' },
  '死亡骑士-邪恶': { statPriority: 'Strength > Mastery > Crit > Haste > Vers', gear: ["Relentless Rider's Crown", "Masterwork Sin'dorei Amulet", 'Shoulderplates of Frozen Blood'], talentPopularity: '0.7%', maxKey: '+24' },
  '恶魔猎手-浩劫': { statPriority: 'Agility > Crit > Mastery > Haste > Vers', gear: ["Devouring Reaver's Intake", "Masterwork Sin'dorei Amulet", "Devouring Reaver's Exhaustplates"], talentPopularity: '7.4%', maxKey: '+22' },
  '恶魔猎手-复仇': { statPriority: 'Agility > Haste > Crit > Mastery > Vers', gear: ["Devouring Reaver's Intake", 'Necklace of the Twisting Void', "Devouring Reaver's Exhaustplates"], talentPopularity: '6.2%', maxKey: '+22' },
  '恶魔猎手-噬灭': { statPriority: 'Agility > Haste > Crit > Mastery > Vers', gear: ["Devouring Reaver's Intake", "Masterwork Sin'dorei Amulet", "Devouring Reaver's Exhaustplates"], talentPopularity: '5.8%', maxKey: '+23' },
  '德鲁伊-平衡': { statPriority: 'Intellect > Mastery > Haste > Crit > Vers', gear: ['Branches of the Luminous Bloom', "Masterwork Sin'dorei Amulet", 'Seedpods of the Luminous Bloom'], talentPopularity: '29.5%', maxKey: '+22' },
  '德鲁伊-野性': { statPriority: 'Agility > Mastery > Haste > Crit > Vers', gear: ['Branches of the Luminous Bloom', "Masterwork Sin'dorei Amulet", 'Seedpods of the Luminous Bloom'], talentPopularity: '73.5%', maxKey: '+23' },
  '德鲁伊-守护': { statPriority: 'Agility > Haste > Vers > Mastery > Crit', gear: ['Branches of the Luminous Bloom', 'Necklace of the Twisting Void', 'Seedpods of the Luminous Bloom'], talentPopularity: '31.0%', maxKey: '+24' },
  '德鲁伊-恢复': { statPriority: 'Intellect > Haste > Mastery > Vers > Crit', gear: ['Branches of the Luminous Bloom', "Masterwork Sin'dorei Amulet", 'Seedpods of the Luminous Bloom'], talentPopularity: '1.9%', maxKey: '+21' },
  '唤魔师-湮灭': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ['Hornhelm of the Black Talon', 'Barbed Ymirheim Choker', 'Beacons of the Black Talon'], talentPopularity: '9.1%', maxKey: '+20' },
  '唤魔师-恩护': { statPriority: 'Intellect > Haste > Crit > Vers > Mastery', gear: ['Hornhelm of the Black Talon', "Masterwork Sin'dorei Amulet", 'Beacons of the Black Talon'], talentPopularity: '1.8%', maxKey: '+22' },
  '唤魔师-增辉': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ["Frenzy's Rebuke", 'Barbed Ymirheim Choker', 'Beacons of the Black Talon'], talentPopularity: '1.1%', maxKey: '+24' },
  '猎人-野兽控制': { statPriority: 'Agility > Crit > Mastery > Haste > Vers', gear: ["Primal Sentry's Maw", "Masterwork Sin'dorei Amulet", 'Scaled Commencement Spaulders'], talentPopularity: '1.9%', maxKey: '+23' },
  '猎人-射击': { statPriority: 'Agility > Crit > Mastery > Haste > Vers', gear: ["Primal Sentry's Maw", "Masterwork Sin'dorei Amulet", 'Scaled Commencement Spaulders'], talentPopularity: '1.3%', maxKey: '+22' },
  '猎人-生存': { statPriority: 'Agility > Mastery > Crit > Haste > Vers', gear: ["Primal Sentry's Maw", "Masterwork Sin'dorei Amulet", 'Scaled Commencement Spaulders'], talentPopularity: '4.4%', maxKey: '+23' },
  '法师-奥术': { statPriority: 'Intellect > Mastery > Crit > Haste > Vers', gear: ["Voidbreaker's Veil", "Masterwork Sin'dorei Amulet", "Voidbreaker's Leyline Nexi"], talentPopularity: '5.2%', maxKey: '+22' },
  '法师-火焰': { statPriority: 'Intellect > Haste > Mastery > Vers > Crit', gear: ["Voidbreaker's Veil", "Masterwork Sin'dorei Amulet", "Voidbreaker's Leyline Nexi"], talentPopularity: '10.8%', maxKey: '+21' },
  '法师-冰霜': { statPriority: 'Intellect > Crit > Mastery > Haste > Vers', gear: ["Voidbreaker's Veil", "Masterwork Sin'dorei Amulet", 'Mantle of Dark Devotion'], talentPopularity: '2.8%', maxKey: '+23' },
  '武僧-酒仙': { statPriority: 'Agility > Crit > Vers > Mastery > Haste', gear: ["Fearsome Visage of Ra-den's Chosen", "Masterwork Sin'dorei Amulet", "Aurastones of Ra-den's Chosen"], talentPopularity: '2.0%', maxKey: '+23' },
  '武僧-织雾': { statPriority: 'Intellect > Haste > Crit > Vers > Mastery', gear: ["Fearsome Visage of Ra-den's Chosen", 'Necklace of the Twisting Void', "Aurastones of Ra-den's Chosen"], talentPopularity: '5.7%', maxKey: '+24' },
  '武僧-踏风': { statPriority: 'Agility > Haste > Crit > Mastery > Vers', gear: ["Fearsome Visage of Ra-den's Chosen", "Masterwork Sin'dorei Amulet", "Aurastones of Ra-den's Chosen"], talentPopularity: '6.8%', maxKey: '+21' },
  '圣骑士-神圣': { statPriority: 'Intellect > Haste > Mastery > Crit > Vers', gear: ["Luminant Verdict's Unwavering Gaze", "Masterwork Sin'dorei Amulet", "Luminant Verdict's Providence Watch"], talentPopularity: '5.5%', maxKey: '+21' },
  '圣骑士-防护': { statPriority: 'Strength > Haste > Crit > Mastery > Vers', gear: ["Luminant Verdict's Unwavering Gaze", 'Barbed Ymirheim Choker', "Luminant Verdict's Providence Watch"], talentPopularity: '1.6%', maxKey: '+22' },
  '圣骑士-惩戒': { statPriority: 'Strength > Crit > Mastery > Haste > Vers', gear: ["Luminant Verdict's Unwavering Gaze", "Masterwork Sin'dorei Amulet", "Luminant Verdict's Providence Watch"], talentPopularity: '2.4%', maxKey: '+23' },
  '牧师-戒律': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ["Blind Oath's Winged Crest", 'Barbed Ymirheim Choker', "Blind Oath's Seraphguards"], talentPopularity: '12.0%', maxKey: '+22' },
  '牧师-神圣': { statPriority: 'Intellect > Crit > Haste > Vers > Mastery', gear: ["Blind Oath's Winged Crest", 'Barbed Ymirheim Choker', "Blind Oath's Seraphguards"], talentPopularity: '4.4%', maxKey: '+21' },
  '牧师-暗影': { statPriority: 'Intellect > Haste > Mastery > Crit > Vers', gear: ["Blind Oath's Winged Crest", "Masterwork Sin'dorei Amulet", "Blind Oath's Seraphguards"], talentPopularity: '1.0%', maxKey: '+23' },
  '潜行者-刺杀': { statPriority: 'Agility > Crit > Haste > Mastery > Vers', gear: ['Masquerade of the Grim Jest', 'Barbed Ymirheim Choker', 'Venom Casks of the Grim Jest'], talentPopularity: '47.0%', maxKey: '+22' },
  '潜行者-狂徒': { statPriority: 'Agility > Crit > Haste > Mastery > Vers', gear: ['Voidlashed Hood', 'Barbed Ymirheim Choker', 'Venom Casks of the Grim Jest'], talentPopularity: '27.3%', maxKey: '+23' },
  '潜行者-敏锐': { statPriority: 'Agility > Mastery > Crit > Haste > Vers', gear: ['Masquerade of the Grim Jest', "Masterwork Sin'dorei Amulet", 'Venom Casks of the Grim Jest'], talentPopularity: '0.5%', maxKey: '+23' },
  '萨满祭司-元素': { statPriority: 'Intellect > Mastery > Crit > Haste > Vers', gear: ['Locus of the Primal Core', "Masterwork Sin'dorei Amulet", 'Tempests of the Primal Core'], talentPopularity: '2.3%', maxKey: '+23' },
  '萨满祭司-增强': { statPriority: 'Agility > Mastery > Haste > Crit > Vers', gear: ['Locus of the Primal Core', "Masterwork Sin'dorei Amulet", 'Tempests of the Primal Core'], talentPopularity: '5.4%', maxKey: '+23' },
  '萨满祭司-恢复': { statPriority: 'Intellect > Crit > Vers > Haste > Mastery', gear: ["Frenzy's Rebuke", 'Barbed Ymirheim Choker', 'Tempests of the Primal Core'], talentPopularity: '3.8%', maxKey: '+23' },
  '术士-痛苦': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ["Abyssal Immolator's Smoldering Flames", 'Barbed Ymirheim Choker', 'Mantle of Dark Devotion'], talentPopularity: '21.7%', maxKey: '+21' },
  '术士-恶魔学识': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ["Abyssal Immolator's Smoldering Flames", 'Barbed Ymirheim Choker', 'Mantle of Dark Devotion'], talentPopularity: '20.4%', maxKey: '+22' },
  '术士-毁灭': { statPriority: 'Intellect > Crit > Haste > Mastery > Vers', gear: ["Abyssal Immolator's Smoldering Flames", 'Barbed Ymirheim Choker', "Abyssal Immolator's Fury"], talentPopularity: '3.9%', maxKey: '+21' },
  '战士-武器': { statPriority: 'Strength > Crit > Haste > Mastery > Vers', gear: ["Night Ender's Tusks", 'Barbed Ymirheim Choker', "Night Ender's Pauldrons"], talentPopularity: '21.2%', maxKey: '+23' },
  '战士-狂怒': { statPriority: 'Strength > Haste > Mastery > Crit > Vers', gear: ["Night Ender's Tusks", "Masterwork Sin'dorei Amulet", "Night Ender's Pauldrons"], talentPopularity: '59.9%', maxKey: '+23' },
  '战士-防护': { statPriority: 'Strength > Haste > Crit > Mastery > Vers', gear: ["Night Ender's Tusks", "Masterwork Sin'dorei Amulet", "Night Ender's Pauldrons"], talentPopularity: '19.0%', maxKey: '+22' }
}

const frostMageRetrievedDetails = {
  talents: {
    sourceName: 'Wowhead',
    sourceUrl: 'https://www.wowhead.com/guide/classes/mage/frost/talent-builds-pve-dps',
    publishedAt: '2026-04-20',
    analysisWindow: 'Midnight Season 1, Patch 12.0.5 Frost Mage talent guide by Dorovon.',
    sourceNote: 'Wowhead lists Spellslinger Mythic+ as a current recommendation and provides a direct talent import code.',
    importCode: 'CAEAAAAAAAAAAAAAAAAAAAAAAMzwYZmZmFmZmYGmZmZmZWMzMMjZAAAgZmZWWmZaDAAWAAAAWAYbbMzMDmthxMjNAAAmZDYmMGwMYA',
    coreTalents: ['Freezing Rain', 'Splitting Ice', 'Fractured Frost', 'Splintering Ray', 'Thermal Void'],
    items: [
      'Hero tree: Spellslinger Mythic+ recommendation from Wowhead.',
      'AoE core: Freezing Rain, Splitting Ice, Fractured Frost and Splintering Ray.',
      'Damage pattern: consume Freezing with Ice Lance around Thermal Void windows.'
    ]
  },
  gear: {
    sourceName: 'Mythicstats + Wowhead',
    sourceUrl: 'https://mythicstats.com/spec/frost-mage',
    publishedAt: '2026-06-09',
    analysisWindow: 'Top 787 Frost Mage Mythic+ logs, 307 unique characters, keys +20 to +23, last two weeks.',
    sourceNote: 'Mythicstats supplies usage rates from top logs; Wowhead item pages supply item names and drop/source details.',
    gear: [
      { slot: '武器', name: 'Umbral Spire of Zuraal', source: 'Mythicstats top main-hand 25.7%; Wowhead: dropped by Zuraal the Ascended.' },
      { slot: '副手', name: "Aln'hara Lantern", source: 'Mythicstats top off-hand 51.5%; Wowhead item 245769.' },
      { slot: '饰品', name: 'Gaze of the Alnseer', source: 'Mythicstats trinket usage 98.7%; Wowhead: dropped by Chimaerus.' },
      { slot: '饰品', name: "Vaelgor's Final Stare", source: 'Mythicstats trinket usage 97.6%; Wowhead: dropped by Vaelgor.' },
      { slot: '头部', name: "Voidbreaker's Veil", source: 'Mythicstats head usage 88.2%; Mage tier set piece from Wowhead.' },
      { slot: '胸部', name: "Voidbreaker's Robe", source: 'Mage tier set chest from Wowhead; Frost 2pc and 4pc bonuses are listed on the item page.' }
    ],
    items: [
      'The two dominant trinkets in the sampled Mythic+ logs are Gaze of the Alnseer and Vaelgor\'s Final Stare.',
      'Voidbreaker tier pieces are valuable because the Frost 2pc improves Flurry and the 4pc improves Shatter through Fingers of Frost.',
      'Treat gear percentages as population evidence, not a replacement for simming the player character.'
    ]
  },
  statWeights: {
    sourceName: 'Archon + Icy Veins',
    sourceUrl: 'https://www.archon.gg/wow/builds/frost/mage/mythic-plus/overview/10/all-dungeons/this-week',
    publishedAt: '2026-06-09',
    analysisWindow: 'Archon: 146,678 parses, all keys +7 and above, last 14 days; page last updated 7 hours before retrieval.',
    sourceNote: 'Archon gives the sampled Mythic+ priority; Icy Veins explains why Frost Mage stat weights are gear-dependent.',
    stats: [
      { name: 'Intellect', value: 'Primary', percent: 100 },
      { name: 'Critical Strike', value: '950', percent: 95 },
      { name: 'Mastery', value: '803', percent: 80 },
      { name: 'Haste', value: '619', percent: 62 },
      { name: 'Versatility', value: '160', percent: 16 }
    ],
    items: [
      'Archon sampled priority: Intellect > Crit > Mastery > Haste > Vers.',
      'Icy Veins notes Frost Mage stat weights change with every gear change, so this is a reference trend.',
      'Use these bars to choose direction, then sim the actual character before expensive crafts or upgrades.'
    ]
  },
  rotation: {
    sourceName: 'Icy Veins + Wowhead',
    sourceUrl: 'https://www.icy-veins.com/wow/frost-mage-pve-dps-rotation-cooldowns-abilities',
    publishedAt: '2026-05-22',
    analysisWindow: 'Icy Veins Frost Mage rotation page for Patch 12.0.5; cross-checked against Wowhead Midnight rotation priority.',
    sourceNote: 'Icy Veins gives opener and AoE priority sequences; Wowhead highlights Ray of Frost timing and Freezing stack usage.',
    rotation: [
      { phase: 'AoE 起手', action: 'Blizzard -> Flurry -> Frozen Orb -> Ray of Frost, then follow normal priority.' },
      { phase: '优先级', action: 'Use Blizzard with Freezing Rain, Flurry on Brain Freeze, then Frozen Orb / Glacial Spike / Ice Lance procs.' },
      { phase: '资源处理', action: 'Use Ice Lance on Fingers of Frost and when Freezing stacks are high enough to avoid wasting Shatter value.' },
      { phase: '爆发窗口', action: 'Plan Ray of Frost so the full channel completes safely; it is a major damage cooldown and builds Freezing stacks.' }
    ],
    items: [
      'Ray of Frost should not be started when incoming mechanics will force a cancel.',
      'Frozen Orb and Blizzard drive the AoE loop; Blizzard is especially important when Freezing Rain is active.',
      'The rotation is priority-based rather than a fixed cast sequence after the opener.'
    ]
  }
}

const retrievedDetailsBySpec = {
  '法师-冰霜': frostMageRetrievedDetails,
  '圣骑士-防护': {
    talents: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/protection/paladin/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Protection Paladin parses in the last 14 days; 5,234 total parses at retrieval.',
      sourceNote: 'Archon recommends the Lightsmith High Keys build from combined Spec and Hero Tree popularity, reaching +22 in the sampled data.',
      coreTalents: ['Lightsmith', "Avenger's Shield", 'Blessed Hammer', 'Grand Crusader', 'Bulwark of Order', 'Guardian of Ancient Kings'],
      items: [
        'Hero tree: Lightsmith was the selected high-key recommendation in the Archon sample.',
        'Core kit: Avenger\'s Shield, Blessed Hammer, Shining Light and Grand Crusader drive Holy Power and interrupts.',
        'Defensive layer: Bulwark of Order, Sentinel, Guardian of Ancient Kings and Ardent Defender are visible in the recommended tree.'
      ]
    },
    gear: {
      sourceName: 'Archon + Wowhead',
      sourceUrl: 'https://www.archon.gg/wow/builds/protection/paladin/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Protection Paladin parses in the last 14 days; gear popularity shown across 5.2k parses.',
      sourceNote: 'Archon lists popular gear from the last two weeks and marks several Paladin tier pieces with Wowhead BiS references.',
      gear: [
        { slot: '头部', name: "Luminant Verdict's Unwavering Gaze", source: 'Archon gear overview: 88.0% popularity, 4.6k parses.' },
        { slot: '肩部', name: "Luminant Verdict's Providence Watch", source: 'Archon gear overview: 82.1% popularity, 4.3k parses.' },
        { slot: '胸部', name: "Luminant Verdict's Divine Warplate", source: 'Archon gear overview: 76.8% popularity, 4k parses.' },
        { slot: '腿部', name: "Luminant Verdict's Greaves", source: 'Archon gear overview: 91.8% popularity, 4.8k parses.' },
        { slot: '武器', name: "Spellbreaker's Blade", source: 'Archon Weapons & Trinkets: 37.0% popularity, 1.9k parses.' },
        { slot: '饰品', name: 'Heart of Ancient Hunger / Gaze of the Alnseer', source: 'Archon trinket rows: both shown at 28.7% popularity, 1.5k parses.' }
      ],
      items: [
        'Four Luminant Verdict tier slots dominate the sampled high-key gear set.',
        'Haste-heavy itemization appears repeatedly across the recommended setup.',
        'Treat trinket percentages as meta usage signals and still sim the actual character when possible.'
      ]
    },
    statWeights: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/protection/paladin/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Protection Paladin parses in the last 14 days.',
      sourceNote: 'Archon sampled priority: Strength > Haste > Crit > Mastery > Vers.',
      stats: [
        { name: 'Strength', value: 'Primary', percent: 100 },
        { name: 'Haste', value: '1020', percent: 100 },
        { name: 'Crit', value: '885', percent: 87 },
        { name: 'Mastery', value: '359', percent: 35 },
        { name: 'Versatility', value: '223', percent: 22 }
      ],
      items: [
        'Haste is the dominant secondary in the retrieved high-key sample.',
        'Crit sits clearly above Mastery and Versatility in the same sample.',
        'Tank gearing still needs survivability checks because available gear can bias aggregate stat bars.'
      ]
    },
    rotation: {
      sourceName: 'Icy Veins + Method',
      sourceUrl: 'https://www.icy-veins.com/wow/protection-paladin-pve-tank-rotation-cooldowns-abilities',
      publishedAt: '2026-05-19',
      analysisWindow: 'Icy Veins Protection Paladin rotation updated for Patch 12.0.5; Method playstyle guide last updated 2026-04-23.',
      sourceNote: 'Icy Veins frames the rotation as Holy Power generation, Shield of the Righteous spending and Consecration uptime; Method highlights Judgment/Blessed Hammer generation and Avenging Wrath windows.',
      rotation: [
        { phase: '基础循环', action: '保持 Consecration，使用 Judgment、Blessed Hammer 和 Avenger\'s Shield 产 Holy Power。' },
        { phase: '生存支出', action: '优先用 Shield of the Righteous 保持护甲覆盖；危险血线或高压波次用 Word of Glory。' },
        { phase: '爆发窗口', action: '把 Divine Toll、Avenging Wrath 和主要伤害技能对齐，用于高危波次或需要快速建立仇恨的拉怪。' },
        { phase: '减伤规划', action: 'Ardent Defender 处理短 CD 尖刺，Guardian of Ancient Kings 留给更高压或机制波次。' }
      ],
      items: [
        '防骑循环不是固定序列，核心是 Holy Power 生成和生存覆盖。',
        'Consecration 覆盖是坦度基础，离开地面效果会明显变脆。',
        '如果追求极限输出，才考虑围绕套装与 Divine Toll 做更细的 Shield of the Righteous 消耗。'
      ]
    }
  },
  '唤魔师-增辉': {
    talents: {
      sourceName: 'Archon + Wowhead',
      sourceUrl: 'https://www.archon.gg/wow/builds/augmentation/evoker/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Augmentation Evoker parses in the last 14 days; 8,823 total parses at retrieval.',
      sourceNote: 'Archon recommends a High Keys build at 40.5% Spec & Hero popularity, reaching +24; Wowhead Mythic+ guide highlights Ebon Might, Prescience and Breath of Eons gameplay.',
      coreTalents: ['Ebon Might', 'Prescience', 'Breath of Eons', 'Eruption', 'Upheaval', 'Obsidian Scales'],
      items: [
        '核心目标是尽量提高 Ebon Might 覆盖，并把 Prescience 给到关键输出位。',
        'Breath of Eons 是大爆发放大窗口，需要跟队友爆发而不是孤立使用。',
        'Archon 高层样本显示增辉在当前热门构筑中仍以团队增益和窗口对齐为核心。'
      ]
    },
    gear: {
      sourceName: 'Archon + Wowhead',
      sourceUrl: 'https://www.archon.gg/wow/builds/augmentation/evoker/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Augmentation Evoker parses in the last 14 days; gear popularity shown across 8.8k parses.',
      sourceNote: 'Archon lists popular gear from the last two weeks and cites Wowhead Augmentation Evoker BiS data for several pieces.',
      gear: [
        { slot: '头部', name: "Frenzy's Rebuke", source: 'Archon gear overview: Crit/Haste, 41.3% popularity, 3.6k parses.' },
        { slot: '肩部', name: 'Beacons of the Black Talon', source: 'Archon gear overview: 92.7% popularity, 8.2k parses.' },
        { slot: '胸部', name: 'Frenzyward of the Black Talon', source: 'Archon gear overview: 93.4% popularity, 8.2k parses.' },
        { slot: '手腕', name: "Farstrider's Plated Bracers", source: 'Archon gear overview: 90.7% popularity, 8k parses.' },
        { slot: '手部', name: "Enforcer's Grips of the Black Talon", source: 'Archon gear overview: 92.6% popularity, 8.2k parses.' },
        { slot: '腿部', name: 'Greaves of the Black Talon', source: 'Archon gear overview: 92.1% popularity, 8.1k parses.' }
      ],
      items: [
        'Black Talon tier pieces dominate the sampled set and should be the first copy-work target.',
        'Crit/Haste appears repeatedly in the recommended setup, matching the retrieved stat priority.',
        'Because Aug value depends on teammates, copy gear as a direction and still validate in real group context.'
      ]
    },
    statWeights: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/augmentation/evoker/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Augmentation Evoker parses in the last 14 days.',
      sourceNote: 'Archon sampled priority: Intellect > Crit > Haste > Mastery > Vers.',
      stats: [
        { name: 'Intellect', value: 'Primary', percent: 100 },
        { name: 'Crit', value: '1322', percent: 100 },
        { name: 'Haste', value: '919', percent: 70 },
        { name: 'Mastery', value: '199', percent: 15 },
        { name: 'Versatility', value: '70', percent: 5 }
      ],
      items: [
        'Crit is the standout secondary in the retrieved high-key sample.',
        'Haste follows as the second major secondary and supports smoother buff cadence.',
        'Mastery and Versatility are far behind in this aggregate, but Aug value can move with team composition.'
      ]
    },
    rotation: {
      sourceName: 'Icy Veins + Wowhead',
      sourceUrl: 'https://www.icy-veins.com/wow/augmentation-evoker-pve-dps-guide/',
      publishedAt: '2026-05-04',
      analysisWindow: 'Icy Veins Augmentation Evoker guide updated for Patch 12.0.5; Wowhead Mythic+ guide updated 2026-04-18.',
      sourceNote: 'Icy Veins covers Patch 12.0.5 Augmentation changes; Wowhead Mythic+ guide emphasizes Ebon Might uptime, Prescience buffing and Breath of Eons timing.',
      rotation: [
        { phase: '开局铺垫', action: '提前给关键队友 Prescience，进入拉怪后尽快建立 Ebon Might 覆盖。' },
        { phase: '核心循环', action: '用 Eruption、Upheaval 和 empowered spells 延长或强化 Ebon Might，并避免资源空转。' },
        { phase: '团队爆发', action: 'Breath of Eons 对齐队友大爆发、饰品或高价值波次，而不是单纯按个人 CD 乱交。' },
        { phase: '工具处理', action: '用 Obsidian Scales、Zephyr、Rescue、Oppressing Roar 等工具覆盖高压机制。' }
      ],
      items: [
        '增辉的输出价值大量体现在队友身上，详情页按 buff 窗口而不是个人 DPS 排列。',
        'Prescience 目标选择比单纯按亮了就按更重要。',
        '高层大秘境中，Breath of Eons 应服务于全队爆发和危险波次。'
      ]
    }
  },
  '牧师-戒律': {
    talents: {
      sourceName: 'Archon + Wowhead',
      sourceUrl: 'https://www.archon.gg/wow/builds/discipline/priest/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Discipline Priest parses in the last 14 days; 5,363 total parses at retrieval.',
      sourceNote: 'Archon recommends the High Keys build at 20.3% Spec & Hero popularity, reaching +22; Wowhead provides Discipline Priest Mythic+ talent build context.',
      coreTalents: ['Power Infusion', 'Mind Blast', 'Improved Purify', 'Mass Dispel', 'Mindpierce', 'Atonement'],
      items: [
        'Archon 推荐树包含 Power Infusion、Mind Blast、Improved Purify、Mass Dispel 等大秘境关键工具。',
        '戒律治疗核心是提前铺 Atonement，再用伤害技能转化治疗，而不是纯读条补血。',
        '高层构筑保留驱散、群驱和控制工具，说明功能性在该专精中占很高权重。'
      ]
    },
    gear: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/discipline/priest/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Discipline Priest parses in the last 14 days; gear popularity shown across 5.3k parses.',
      sourceNote: 'Archon lists popular Discipline Priest gear from the last two weeks with item popularity and parse counts.',
      gear: [
        { slot: '头部', name: "Blind Oath's Winged Crest", source: 'Archon gear overview: 84.3% popularity, 4.5k parses.' },
        { slot: '肩部', name: "Blind Oath's Seraphguards", source: 'Archon gear overview: 85.4% popularity, 4.6k parses.' },
        { slot: '披风', name: "Adherent's Silken Shroud", source: 'Archon gear overview: 47.7% popularity, 2.6k parses.' },
        { slot: '胸部', name: "Blind Oath's Raiment", source: 'Archon gear overview: 77.2% popularity, 4.1k parses.' },
        { slot: '手腕', name: "Martyr's Bindings", source: 'Archon gear overview: 56.3% popularity, 3k parses.' },
        { slot: '腿部', name: "Blind Oath's Leggings", source: 'Archon gear overview: 90.7% popularity, 4.9k parses.' }
      ],
      items: [
        'Blind Oath tier pieces are the clear copy-work baseline in high-key samples.',
        'Haste/Crit and Mastery/Haste pairings show up across the dominant gear rows.',
        '治疗装备选择仍要结合队伍压力模型，不能只看单一输出样本。'
      ]
    },
    statWeights: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/discipline/priest/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Discipline Priest parses in the last 14 days.',
      sourceNote: 'Archon sampled priority: Intellect > Crit > Haste > Mastery > Vers.',
      stats: [
        { name: 'Intellect', value: 'Primary', percent: 100 },
        { name: 'Crit', value: '938', percent: 100 },
        { name: 'Haste', value: '853', percent: 91 },
        { name: 'Mastery', value: '663', percent: 71 },
        { name: 'Versatility', value: '109', percent: 12 }
      ],
      items: [
        'Crit and Haste 是该样本下最接近的两个副属性方向。',
        'Mastery 仍有明显价值，特别是治疗专精不能只用伤害视角评价。',
        'Versatility 在聚合样本中最低，但高层生存压力可能改变个人选择。'
      ]
    },
    rotation: {
      sourceName: 'Wowhead + Archon',
      sourceUrl: 'https://www.wowhead.com/guide/classes/priest/discipline/rotation-cooldowns-pve-healer',
      publishedAt: '2026-05-26',
      analysisWindow: 'Wowhead Discipline Priest rotation guide for Midnight Season 1; Archon high-key sample retrieved 2026-06-09.',
      sourceNote: 'Wowhead frames Discipline around optimal cooldown and cadence across talent builds; Archon validates the high-key talent and stat trend.',
      rotation: [
        { phase: '伤害前准备', action: '提前用 Power Word: Shield、Renew 或相关技能铺 Atonement，不要等全队掉血后再开始。' },
        { phase: '治疗转化', action: '在 Atonement 覆盖期用 Mind Blast、Penance、Smite 等伤害技能转化团队治疗。' },
        { phase: '高压波次', action: '把 Rapture、Pain Suppression、Power Word: Barrier 等大技能留给预判到的尖刺。' },
        { phase: '大秘境工具', action: 'Mass Dispel、Improved Purify、Psychic Scream 和 Power Infusion 按副本机制与队友爆发安排。' }
      ],
      items: [
        '戒律不是反应式奶法，UI 中按“预铺 -> 转化 -> 高压 CD”展示。',
        'Power Infusion 和 Mass Dispel 属于该专精在高层队伍中的核心功能价值。',
        '如果玩家总是在掉血后才铺 Atonement，构筑正确也很难打出高端效果。'
      ]
    }
  },
  '死亡骑士-鲜血': {
    talents: {
      sourceName: 'Archon + Method',
      sourceUrl: 'https://www.archon.gg/wow/builds/blood/death-knight/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Blood Death Knight parses in the last 14 days; 3,732 total parses at retrieval.',
      sourceNote: 'Archon recommends the Deathbringer High Keys build at 32.9% Spec & Hero popularity, reaching +22; Method highlights Deathbringer opener and Dancing Rune Weapon planning.',
      coreTalents: ['Deathbringer', 'Death Strike', 'Dancing Rune Weapon', "Reaper's Mark", 'Icebound Fortitude', 'Anti-Magic Zone'],
      items: [
        'Hero tree: Deathbringer is the retrieved high-key recommendation.',
        'Core loop revolves around Death Strike timing, Runic Power management and cooldown planning.',
        'Archon 推荐树包含 Icebound Fortitude、Anti-Magic Zone、Mind Freeze 等高层功能点。'
      ]
    },
    gear: {
      sourceName: 'Archon + Wowhead',
      sourceUrl: 'https://www.archon.gg/wow/builds/blood/death-knight/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Blood Death Knight parses in the last 14 days; gear popularity shown across 3.7k parses.',
      sourceNote: 'Archon lists popular Blood Death Knight gear from the last two weeks and cites Wowhead Blood Death Knight BiS data for several pieces.',
      gear: [
        { slot: '头部', name: "Relentless Rider's Crown", source: 'Archon gear overview: 78.4% popularity, 2.9k parses.' },
        { slot: '肩部', name: "Relentless Rider's Dreadthorns", source: 'Archon gear overview: 79.8% popularity, 3k parses.' },
        { slot: '胸部', name: "Relentless Rider's Cuirass", source: 'Archon gear overview: 76.3% popularity, 2.8k parses.' },
        { slot: '手腕', name: "Spellbreaker's Bracers", source: 'Archon gear overview: 70.9% popularity, 2.6k parses.' },
        { slot: '手部', name: "Relentless Rider's Bonegrasps", source: 'Archon gear overview: 71.8% popularity, 2.7k parses.' },
        { slot: '腿部', name: "Relentless Rider's Legguards", source: 'Archon gear overview: 88.6% popularity, 3.3k parses.' }
      ],
      items: [
        'Relentless Rider tier pieces are the dominant sampled set.',
        'Mastery-heavy gems and Haste/Mastery itemization both appear in the retrieved high-key gear rows.',
        '血 DK 装备必须结合可承伤节奏理解，不能只看伤害排序。'
      ]
    },
    statWeights: {
      sourceName: 'Archon',
      sourceUrl: 'https://www.archon.gg/wow/builds/blood/death-knight/mythic-plus/overview/high-keys/all-dungeons/this-week',
      publishedAt: '2026-06-09',
      analysisWindow: 'Archon High Keys Mythic+, top 5% of Blood Death Knight parses in the last 14 days.',
      sourceNote: 'Archon sampled priority: Strength > Mastery > Vers > Crit > Haste.',
      stats: [
        { name: 'Strength', value: 'Primary', percent: 100 },
        { name: 'Mastery', value: '774', percent: 100 },
        { name: 'Versatility', value: '660', percent: 85 },
        { name: 'Crit', value: '604', percent: 78 },
        { name: 'Haste', value: '446', percent: 58 }
      ],
      items: [
        'Mastery 是该高层样本下最强副属性方向。',
        'Versatility 与 Crit 接近，分别服务于承伤稳定和输出/招架收益。',
        'Haste 在该聚合样本中最低，但具体角色仍受装备池与副本压力影响。'
      ]
    },
    rotation: {
      sourceName: 'Method + Wowhead',
      sourceUrl: 'https://www.method.gg/guides/blood-death-knight/playstyle-and-rotation',
      publishedAt: '2026-04-21',
      analysisWindow: 'Method Blood Death Knight playstyle guide updated for Midnight 12.0.5; Wowhead Blood Death Knight rotation guide for Midnight Season 1.',
      sourceNote: 'Method notes Deathbringer opener prioritizes Reaper\'s Mark before Dancing Rune Weapon and keeps cooldowns synced; Wowhead emphasizes cooldown cadence for Blood.',
      rotation: [
        { phase: '开怪建立', action: 'Deathbringer 构筑先用 Reaper\'s Mark，再接 Dancing Rune Weapon，使后续冷却保持同步。' },
        { phase: '核心生存', action: '用 Death Strike 回应真实承伤，避免在低伤害窗口浪费 Runic Power。' },
        { phase: '符文循环', action: 'Heart Strike、Blood Boil 和骨盾相关技能用于资源、仇恨和群体压力维持。' },
        { phase: '高压规划', action: 'Icebound Fortitude、Vampiric Blood、Anti-Magic Zone 等按副本尖刺提前安排。' }
      ],
      items: [
        '血 DK 的关键不是固定按键顺序，而是 Death Strike 是否打在有效承伤之后。',
        'Dancing Rune Weapon 与 Reaper\'s Mark 的同步是 Deathbringer 构筑的重要节奏点。',
        '高层中自疗窗口、符文能量池和减伤链条比单纯 DPS 更重要。'
      ]
    }
  }
}

function archonBuildUrl(specialization) {
  const specSlug = specSlugByName[specialization.specName]
  const classSlug = classSlugByName[specialization.className]
  return `https://www.archon.gg/wow/builds/${specSlug}/${classSlug}/mythic-plus/overview/high-keys/all-dungeons/this-week`
}

function wowheadGuideUrl(specialization, guide) {
  const specSlug = specSlugByName[specialization.specName]
  const classSlug = classSlugByName[specialization.className]
  return `https://www.wowhead.com/guide/classes/${classSlug}/${specSlug}/${guide}`
}

function icyVeinsGuideUrl(specialization, guide) {
  const specSlug = specSlugByName[specialization.specName]
  const classSlug = classSlugByName[specialization.className]
  return `https://www.icy-veins.com/wow/${specSlug}-${classSlug}-pve-${guide}`
}

function roleStatRows(role) {
  const rows = statPriorityByRole[role] || statPriorityByRole['近战输出']
  return rows.map(([name, value, percent]) => ({ name, value, percent }))
}

function snapshotFor(specialization) {
  return archonSnapshots[specialization.id]
}

function statRowsFromSnapshot(snapshot, role) {
  if (!snapshot) return roleStatRows(role)
  return snapshot.statPriority.split(' > ').map((name, index) => ({
    name,
    value: index === 0 ? 'Primary' : `Archon #${index + 1}`,
    percent: Math.max(28, 100 - index * 14)
  }))
}

function roleRotationRows(role) {
  const rows = rotationByRole[role] || rotationByRole['近战输出']
  return rows.map(([phase, action]) => ({ phase, action }))
}

function genericTalentHighlights(specialization) {
  const label = specialization.title
  const snapshot = snapshotFor(specialization)
  return [
    snapshot ? `Archon 推荐树 ${snapshot.talentPopularity}` : `${label} Archon High Keys`,
    snapshot ? `最高样本 ${snapshot.maxKey}` : `${label} Wowhead Mythic+`,
    snapshot ? snapshot.statPriority : `${specialization.role}核心循环`,
    snapshot?.gear?.[0] || '高层大秘境功能点',
    snapshot?.gear?.[1] || '团本/大秘境场景差异'
  ]
}

function genericGearRows(specialization) {
  const label = specialization.title
  const archonUrl = archonBuildUrl(specialization)
  const snapshot = snapshotFor(specialization)
  const snapshotRows = snapshot ? snapshot.gear.map((name, index) => ({
    slot: ['热门装备', '项链/副槽', '套装/肩部'][index] || '热门装备',
    name,
    source: `Archon high-keys gear snapshot: ${snapshot.statPriority}; recommended tree ${snapshot.talentPopularity}, max key ${snapshot.maxKey}.`
  })) : []
  return [
    ...snapshotRows,
    { slot: '武器/饰品', name: `${label} Archon 武器与饰品表`, source: `Archon weapons and trinkets table: ${archonUrl}`, isReference: true, metadataStatus: 'source_reference' },
    { slot: '制作', name: `${label} 制造与低保优先级`, source: `Wowhead gearing guide: ${wowheadGuideUrl(specialization, 'bis-gear')}`, isReference: true, metadataStatus: 'source_reference' }
  ].slice(0, Math.max(4, snapshotRows.length + 2))
}

function sourceBackedDetailsForQuery(specialization, queryType) {
  const archonUrl = archonBuildUrl(specialization)
  const label = specialization.title
  const snapshot = snapshotFor(specialization)

  if (queryType.key === 'talents') {
    return {
      key: queryType.key,
      title: `${label} · ${queryType.title}`,
      desc: queryType.desc,
      sourceName: 'Archon + Wowhead',
      sourceUrl: archonUrl,
      publishedAt: latestAnalysis.publishedAt,
      analysisWindow: `${latestAnalysis.analysisWindow}；Archon High Keys 构筑页快照：推荐树热度 ${snapshot?.talentPopularity || '见来源页'}，最高样本 ${snapshot?.maxKey || '见来源页'}。`,
      sourceNote: `Archon 提供 ${label} 高层大秘境构筑入口，Wowhead 提供职业专精天赋说明和场景拆分。`,
      coreTalents: genericTalentHighlights(specialization),
      items: [
        `Archon High Keys 页面用于校验 ${label} 在近 14 天高层样本中的构筑方向；当前快照热度 ${snapshot?.talentPopularity || '以来源页为准'}。`,
        `Wowhead ${label} Mythic+ 指南用于解释天赋选择、场景差异和核心循环目的。`,
        `${specialization.role}专精优先保留高层大秘境中影响生存、输出或团队功能的节点。`
      ]
    }
  }

  if (queryType.key === 'gear') {
    return {
      key: queryType.key,
      title: `${label} · ${queryType.title}`,
      desc: queryType.desc,
      sourceName: 'Archon + Wowhead',
      sourceUrl: archonUrl,
      publishedAt: latestAnalysis.publishedAt,
      analysisWindow: `${latestAnalysis.analysisWindow}；装备来源取 Archon 高层装备快照与 Wowhead BiS/装备指南交叉校验。`,
      sourceNote: `Archon 提供 ${label} 高层装备、武器、饰品热度入口，Wowhead 用于校验装备获取和 BiS 说明。`,
      gear: genericGearRows(specialization),
      items: [
        snapshot ? `当前 Archon 快照前三件热门装备：${snapshot.gear.join('、')}。` : `${label} 装备模块优先看套装、饰品、武器和制造/低保四类决策。`,
        'Archon 热度代表高层玩家选择趋势，不等于每个角色的最终 Sim 结果。',
        '玩家抄作业时应先匹配可获取装备，再用角色模拟校验升级优先级。'
      ]
    }
  }

  if (queryType.key === 'statWeights') {
    return {
      key: queryType.key,
      title: `${label} · ${queryType.title}`,
      desc: queryType.desc,
      sourceName: 'Archon + Warcraft Logs',
      sourceUrl: archonUrl,
      publishedAt: latestAnalysis.publishedAt,
      analysisWindow: `${latestAnalysis.analysisWindow}；属性趋势取 Archon 高层构筑快照：${snapshot?.statPriority || '见来源页'}。`,
      sourceNote: `Archon 的 ${label} high-keys 页面给出高端样本属性方向，WCL 样本用于解释表现边界。`,
      stats: statRowsFromSnapshot(snapshot, specialization.role),
      items: [
        snapshot ? `Archon 当前快照属性顺序：${snapshot.statPriority}。` : `${label} 属性条展示的是高层构筑方向，不替代角色级 Sim。`,
        `${specialization.role}专精的属性收益会受装等、套装、饰品和副本压力影响。`,
        '高价值制造、附魔和宝石调整前，应结合当前角色装备重新模拟。'
      ]
    }
  }

  return {
    key: queryType.key,
    title: `${label} · ${queryType.title}`,
    desc: queryType.desc,
    sourceName: 'Icy Veins + Wowhead',
    sourceUrl: icyVeinsGuideUrl(specialization, specialization.role === '治疗' ? 'healer-guide' : specialization.role === '坦克' ? 'tank-guide' : 'dps-guide'),
    publishedAt: latestAnalysis.publishedAt,
    analysisWindow: `${latestAnalysis.analysisWindow}；循环解释取 Icy Veins / Wowhead 职业专精指南并结合高层样本场景。`,
    sourceNote: `Icy Veins 与 Wowhead 提供 ${label} 的 opener、优先级、冷却规划和大秘境场景说明。`,
    rotation: roleRotationRows(specialization.role),
    items: [
      `${label} 循环模块按玩家实际操作顺序拆成起手、核心循环、资源处理和高压场景。`,
      '固定循环只适合开局；大秘境和团本都应按机制、资源和爆发窗口动态调整。',
      '高端玩家抄作业的关键是理解技能为什么留给某个波次，而不是只记按键顺序。'
    ]
  }
}

function makeDetails(specialization) {
  const retrievedDetails = retrievedDetailsBySpec[specialization.id]

  return queryTypes.reduce((details, queryType) => {
    if (retrievedDetails) {
      const retrieved = retrievedDetails[queryType.key]
      details[queryType.key] = {
        key: queryType.key,
        title: `${specialization.title} · ${queryType.title}`,
        desc: queryType.desc,
        ...retrieved
      }
      return details
    }

    details[queryType.key] = sourceBackedDetailsForQuery(specialization, queryType)
    return details
  }, {})
}

function getSpecializationDetail(id) {
  const specialization = specializations.find((item) => item.id === id)
  if (!specialization) return null
  const season = buildCurrentSeasonPayload()
  return {
    ...specialization,
    details: makeDetails(specialization),
    ...seasonMetadataFields(season)
  }
}

function buildSpecializationHomePayload() {
  const season = buildCurrentSeasonPayload()

  return {
    navTitle: '职业专精',
    kicker: '职业控制台',
    title: '职业专精',
    desc: '追踪最高端大秘境、团本和 WCL 数据，首版先沉淀可直接参考的天赋与装备作业。',
    quickActions: firstVersionHomeActions,
    classOptions,
    featuredSpecializations: [],
    trustedSources: trustedBuildSources,
    lastAnalyzedAt: latestAnalysis.publishedAt,
    analysisWindow: latestAnalysis.analysisWindow,
    ...seasonMetadataFields(season)
  }
}

function buildFeaturedSpecializations() {
  return featuredIds
    .map((id) => specializations.find((item) => item.id === id))
    .filter(Boolean)
    .map((item) => ({
      ...item,
      desc: `${item.desc} 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。`
    }))
}

function buildSpecializationIntelPayload() {
  const season = buildCurrentSeasonPayload()
  const items = buildFeaturedSpecializations()

  return {
    navTitle: '热门专精',
    title: '热门专精资讯',
    desc: '展示当前已获取并保留来源证据的热门专精趋势，点击可进入对应专精的天赋构筑详情。',
    count: items.length,
    items,
    trustedSources: trustedBuildSources,
    lastAnalyzedAt: latestAnalysis.publishedAt,
    analysisWindow: latestAnalysis.analysisWindow,
    ...seasonMetadataFields(season)
  }
}

module.exports = {
  buildSpecializationHomePayload,
  buildSpecializationIntelPayload,
  getSpecializationDetail,
  queryTypes,
  trustedBuildSources
}
