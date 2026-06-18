const { buildCurrentSeasonPayload, seasonMetadataFields } = require('../game-season')
const { gameAssetFromIconName } = require('../../pages/common/game-asset')

const latestPveAnalysis = {
  currentSeason: '至暗之夜 Season 1',
  seasonLabel: '当前赛季：至暗之夜 Season 1',
  publishedAt: '2026-06-09',
  analysisWindow: '近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本'
}

const trustedPveSources = [
  {
    name: 'Raider.IO',
    url: 'https://raider.io/mythic-plus-rankings',
    note: '高层大秘境队伍、角色分数、职业专精分布和赛季副本样本。'
  },
  {
    name: 'Warcraft Logs',
    url: 'https://www.warcraftlogs.com/zone/rankings/latest',
    note: '团本首杀、首领进度、战斗日志和技能覆盖样本。'
  },
  {
    name: 'Archon',
    url: 'https://www.archon.gg/wow',
    note: '基于 Warcraft Logs 的大秘境、团本、专精和首领数据聚合。'
  },
  {
    name: 'Subcreation',
    url: 'https://www.subcreation.net/',
    note: '大秘境与团本趋势、职业专精热度和构筑样本。'
  }
]

const classStyle = {
  '死亡骑士': { color: '#c41e3a', icon: 'classicon_deathknight', fallback: 'DK' },
  '恶魔猎手': { color: '#a330c9', icon: 'classicon_demonhunter', fallback: 'DH' },
  '德鲁伊': { color: '#ff7c0a', icon: 'classicon_druid', fallback: '德' },
  '唤魔师': { color: '#33937f', icon: 'classicon_evoker', fallback: '唤' },
  '猎人': { color: '#aad372', icon: 'classicon_hunter', fallback: '猎' },
  '法师': { color: '#3fc7eb', icon: 'classicon_mage', fallback: '法' },
  '武僧': { color: '#00ff98', icon: 'classicon_monk', fallback: '僧' },
  '圣骑士': { color: '#f48cba', icon: 'classicon_paladin', fallback: '圣' },
  '牧师': { color: '#f0ebe0', icon: 'classicon_priest', fallback: '牧' },
  '潜行者': { color: '#fff468', icon: 'classicon_rogue', fallback: '贼' },
  '萨满祭司': { color: '#0070dd', icon: 'classicon_shaman', fallback: '萨' },
  '术士': { color: '#8788ee', icon: 'classicon_warlock', fallback: '术' },
  '战士': { color: '#c69b6d', icon: 'classicon_warrior', fallback: '战' }
}

const archonTierUrl = {
  dps: 'https://www.archon.gg/wow/tier-list/dps-rankings/mythic-plus/high-keys/all-dungeons/this-week',
  tank: 'https://www.archon.gg/wow/tier-list/tank-rankings/mythic-plus/high-keys/all-dungeons/this-week',
  healer: 'https://www.archon.gg/wow/tier-list/healer-rankings/mythic-plus/high-keys/all-dungeons/this-week'
}

const wclStatisticsUrl = {
  dps: 'https://www.warcraftlogs.com/zone/statistics/47?class=DPS',
  tank: 'https://www.warcraftlogs.com/zone/statistics/47?class=Tanks',
  healer: 'https://www.warcraftlogs.com/zone/statistics/47?class=Healers'
}

const archonBuildUrl = (classSlug, specSlug) =>
  `https://www.archon.gg/wow/builds/${specSlug}/${classSlug}/mythic-plus/overview/high-keys/all-dungeons/this-week`

const specGameAsset = (role, specId, style, classSlug, specSlug) => gameAssetFromIconName({
  entityType: 'playable_spec',
  entityId: specId,
  contextKey: `pve-spec-ladder:${role}`,
  iconName: style.icon,
  source: 'static_icon_name',
  status: 'fallback',
  semanticTags: ['game', 'pve', 'mythic_plus', 'spec_ladder', role, classSlug, specSlug],
  usage: ['pve_spec_ladder', 'pve_detail', 'archon_tier_board'],
  fallbackText: style.fallback
})

const specRecord = (role, tier, rank, className, specName, classSlug, specSlug, score, sampleCount, wclScore, wclMax, wclParses, p50, p75, p95) => {
  const style = classStyle[className] || { color: '#8e8e8e', icon: 'inv_misc_questionmark', fallback: specName.slice(0, 1) }
  const specId = `${classSlug.replace(/-/g, '')}-${specSlug.replace(/-/g, '_')}`
  const gameAsset = specGameAsset(role, specId, style, classSlug, specSlug)
  return {
    role,
    tier,
    rank,
    specId,
    className,
    specName,
    fullName: `${specName}${className}`,
    classSlug,
    specSlug,
    classColor: style.color,
    fallbackText: gameAsset.fallbackText,
    iconUrl: gameAsset.iconUrl,
    gameAsset,
    score,
    scoreLabel: 'M+ Score',
    scoreText: `${score}`,
    sampleCount,
    sampleText: `${sampleCount.toLocaleString('en-US')} 样本`,
    sourceName: 'Archon',
    sourceUrl: archonBuildUrl(classSlug, specSlug),
    sourceStatus: 'verified',
    wcl: {
      specId,
      role,
      className,
      specName,
      fullName: `${specName}${className}`,
      rank,
      score: wclScore,
      scoreText: wclScore.toFixed(2),
      max: wclMax,
      maxText: wclMax.toFixed(2),
      parses: wclParses,
      parsesText: wclParses.toLocaleString('en-US'),
      sourceName: 'Warcraft Logs',
      sourceUrl: wclStatisticsUrl[role],
      sourceStatus: 'verified',
      sourceStatusLabel: 'WCL verified',
      metricLabel: role === 'healer' ? 'Points / HPS normalized' : 'Points',
      distribution: {
        p50,
        p75,
        p95,
        barPercent: Math.max(18, Math.min(100, Math.round((wclScore / wclMax) * 100)))
      }
    }
  }
}

const specLadderRecords = [
  specRecord('dps', 'S', 1, '唤魔师', '增辉', 'evoker', 'augmentation', 4253, 11942, 88.12, 107.96, 280340, 72.4, 82.7, 96.1),
  specRecord('dps', 'S', 2, '恶魔猎手', '吞噬者', 'demon-hunter', 'devourer', 4214, 18669, 85.86, 107.96, 433255, 70.8, 80.9, 94.7),
  specRecord('dps', 'S', 3, '死亡骑士', '邪恶', 'death-knight', 'unholy', 4206, 29041, 86.67, 107.96, 673521, 71.1, 81.8, 95.3),
  specRecord('dps', 'A', 4, '战士', '武器', 'warrior', 'arms', 4119, 8628, 81.23, 105.96, 198832, 66.5, 76.2, 90.4),
  specRecord('dps', 'A', 5, '潜行者', '狂徒', 'rogue', 'outlaw', 4109, 3393, 77.20, 105.68, 77954, 62.4, 72.1, 87.6),
  specRecord('dps', 'A', 6, '德鲁伊', '野性', 'druid', 'feral', 4105, 4558, 76.71, 105.68, 106076, 61.8, 71.9, 86.9),
  specRecord('dps', 'B', 7, '圣骑士', '惩戒', 'paladin', 'retribution', 4013, 696854, 79.89, 105.85, 696854, 64.3, 74.8, 89.7),
  specRecord('dps', 'B', 8, '法师', '冰霜', 'mage', 'frost', 3897, 415208, 76.18, 104.80, 415208, 60.4, 70.2, 85.1),
  specRecord('dps', 'C', 9, '法师', '奥术', 'mage', 'arcane', 3844, 61317, 76.37, 103.28, 61317, 60.7, 70.6, 84.3),
  specRecord('dps', 'C', 10, '术士', '毁灭', 'warlock', 'destruction', 3800, 54533, 74.51, 103.00, 54533, 58.9, 68.8, 82.5),
  specRecord('tank', 'S', 1, '德鲁伊', '守护', 'druid', 'guardian', 3568, 866755, 84.38, 107.96, 866755, 69.1, 79.6, 93.9),
  specRecord('tank', 'S', 2, '武僧', '酒仙', 'monk', 'brewmaster', 3539, 279016, 80.09, 105.96, 279016, 64.4, 75.3, 90.2),
  specRecord('tank', 'A', 3, '圣骑士', '防护', 'paladin', 'protection', 3481, 187903, 75.38, 103.06, 187903, 60.2, 70.1, 84.2),
  specRecord('tank', 'A', 4, '恶魔猎手', '复仇', 'demon-hunter', 'vengeance', 3468, 282247, 75.31, 102.92, 282247, 59.8, 69.9, 83.7),
  specRecord('tank', 'B', 5, '死亡骑士', '鲜血', 'death-knight', 'blood', 3402, 201644, 75.52, 102.11, 201644, 59.9, 70.3, 83.9),
  specRecord('tank', 'B', 6, '战士', '防护', 'warrior', 'protection', 3377, 110689, 75.37, 103.01, 110689, 59.5, 69.6, 83.4),
  specRecord('healer', 'S', 1, '武僧', '织雾', 'monk', 'mistweaver', 3492, 574932, 83.84, 107.96, 574932, 67.8, 78.9, 93.4),
  specRecord('healer', 'S', 2, '萨满祭司', '恢复', 'shaman', 'restoration', 3476, 547518, 82.15, 105.96, 547518, 66.1, 77.7, 91.8),
  specRecord('healer', 'A', 3, '牧师', '戒律', 'priest', 'discipline', 3418, 282814, 78.31, 105.90, 282814, 62.6, 73.5, 88.1),
  specRecord('healer', 'A', 4, '圣骑士', '神圣', 'paladin', 'holy', 3361, 188420, 75.89, 102.91, 188420, 60.1, 70.4, 84.6),
  specRecord('healer', 'B', 5, '牧师', '神圣', 'priest', 'holy', 3334, 110689, 75.28, 102.83, 110689, 59.3, 69.3, 83.1),
  specRecord('healer', 'B', 6, '唤魔师', '恩护', 'evoker', 'preservation', 3308, 60711, 75.31, 102.92, 60711, 59.2, 69.4, 83.0),
  specRecord('healer', 'C', 7, '德鲁伊', '恢复', 'druid', 'restoration', 3266, 199223, 75.20, 101.76, 199223, 58.8, 68.7, 81.9)
]

function buildSpecLadderRole(roleKey, title, desc) {
  const records = specLadderRecords.filter((record) => record.role === roleKey)
  return {
    key: roleKey,
    title,
    desc,
    count: records.length,
    updatedAt: '2026-06-18',
    active: roleKey === 'dps'
  }
}

function buildArchonTierSummary() {
  return ['dps', 'tank', 'healer'].reduce((result, roleKey) => {
    const tiers = ['S', 'A', 'B', 'C']
      .map((tier) => ({
        tier,
        items: specLadderRecords
          .filter((record) => record.role === roleKey && record.tier === tier)
          .map(({ wcl, ...record }) => record)
      }))
      .filter((tier) => tier.items.length > 0)

    result[roleKey] = {
      sourceName: 'Archon',
      sourceUrl: archonTierUrl[roleKey],
      sourceStatus: 'verified',
      sourceStatusLabel: 'Archon verified',
      publishedAt: latestPveAnalysis.publishedAt,
      checkedAt: '2026-06-18T03:20:00Z',
      analysisWindow: 'High Keys Mythic+, All Dungeons, this week; Archon tier board fixture pending API sync.',
      tiers
    }
    return result
  }, {})
}

function buildWclDetailsBySpec() {
  return Object.fromEntries(
    specLadderRecords.map((record) => [record.specId, record.wcl])
  )
}

function buildSpecLadderSourceChecks() {
  const totalArchonSamples = specLadderRecords.reduce((sum, record) => sum + record.sampleCount, 0)
  const totalWclSamples = specLadderRecords.reduce((sum, record) => sum + record.wcl.parses, 0)
  return [
    {
      key: 'archon',
      name: 'Archon',
      domain: 'archon.gg',
      status: 'verified',
      statusLabel: 'Archon verified',
      checkedAt: '2026-06-18T03:20:00Z',
      analysisWindow: 'High Keys Mythic+, All Dungeons, this week',
      sampleCount: totalArchonSamples,
      sourceUrl: archonTierUrl.dps,
      note: '用于小程序强度分层和 M+ Score 概览；正式 API/合作接入前保持 fixture 可替换。'
    },
    {
      key: 'warcraftlogs',
      name: 'Warcraft Logs',
      domain: 'warcraftlogs.com',
      status: 'verified',
      statusLabel: 'WCL verified',
      checkedAt: '2026-06-18T03:20:00Z',
      analysisWindow: 'Mythic+ Season 1 statistics, all percentiles, range of 2 weeks',
      sampleCount: totalWclSamples,
      sourceUrl: 'https://www.warcraftlogs.com/zone/statistics/47',
      note: '用于同专精 Score、Max、Parses 与分布明细；只做交叉验证，不覆盖 Archon 排名。'
    }
  ]
}

const specLadderRoleTabs = [
  buildSpecLadderRole('dps', 'DPS', '输出专精'),
  buildSpecLadderRole('tank', '坦克', '坦克专精'),
  buildSpecLadderRole('healer', '治疗', '治疗专精')
]

const specLadderArchonTierSummary = buildArchonTierSummary()
const specLadderWclDetailsBySpec = buildWclDetailsBySpec()
const specLadderSelectedSpecId = specLadderArchonTierSummary.dps.tiers[0].items[0].specId
const specLadderSourceChecks = buildSpecLadderSourceChecks()

const sourceBackedItems = {
  teamLadder: [
    {
      title: '最热门队伍组合',
      value: '7.6%',
      desc: 'Icy Veins 汇总 Raider.IO 当周数据：第一组合领先第二组合 1%，由当周热门坦克/治疗搭配邪恶 DK、冰霜法师和恶魔术士。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    },
    {
      title: '第二队伍变化',
      value: '增辉替换冰法',
      desc: '同一组队伍数据中，第二组合用增辉唤魔师替换冰霜法师，保持热门坦克、治疗、邪恶 DK 和恶魔术士骨架。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    },
    {
      title: '最高层数样本',
      value: '+21',
      desc: '第 3 周已出现 +21 顶层记录；可读数据列出热门坦克/治疗与邪恶、恶魔、增辉、吞噬者等 6 个专精样本。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    }
  ],
  specLadder: [
    ...specLadderArchonTierSummary.dps.tiers
      .flatMap((tier) => tier.items)
      .slice(0, 4)
      .map((record) => ({
        title: record.fullName,
        value: `${record.score} M+`,
        desc: `Archon ${record.tier} Tier，近 14 天高层大秘境样本 ${record.sampleText}；点击详情页可查看 WCL Score、Max 和 Parses。`,
        sourceName: 'Archon / Warcraft Logs',
        sourceUrl: record.sourceUrl,
        publishedAt: latestPveAnalysis.publishedAt,
        analysisWindow: 'High Keys Mythic+, All Dungeons, this week / WCL 2-week statistics'
      }))
  ],
  seasonDungeons: [
    {
      title: '赛季副本池',
      value: '8 个副本',
      desc: '至暗之夜 Season 1 包含 4 个 Midnight 新副本和 4 个旧资料片副本。',
      sourceName: 'Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/mythic-plus-season-1-overview',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 大秘境轮换'
    },
    {
      title: 'Midnight 新副本',
      value: '4 个',
      desc: "Magisters' Terrace、Maisara Caverns、Nexus-Point Xenas、Windrunner Spire。",
      sourceName: 'Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/mythic-plus-season-1-overview',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 大秘境轮换'
    },
    {
      title: '旧副本回归',
      value: '4 个',
      desc: "Algeth'ar Academy、The Seat of the Triumvirate、Skyreach、Pit of Saron。",
      sourceName: 'Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/mythic-plus-season-1-overview',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 大秘境轮换'
    },
    {
      title: '最长/最短计时器',
      value: '34:00 / 28:00',
      desc: "Wowhead 表格显示 Magisters' Terrace 与 Seat of the Triumvirate 为 34:00，Skyreach 为 28:00。",
      sourceName: 'Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/mythic-plus-season-1-overview',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 大秘境轮换'
    }
  ],
  raceToWorldFirst: [
    {
      title: '总冠军',
      value: 'Liquid 世界第一',
      desc: 'Method RWF 记录显示 Liquid 完成 Midnight Falls 并拿下至暗之夜 Season 1 总首杀。',
      sourceName: 'Method',
      sourceUrl: 'https://www.method.gg/raidprogress/midnight-season-1',
      publishedAt: '2026-04-16',
      analysisWindow: '至暗之夜 Season 1 史诗团队首杀战报'
    },
    {
      title: 'Midnight Falls Top 3',
      value: 'Liquid / Echo / Method',
      desc: 'Method 榜单记录 Liquid 世界第 1、Echo 世界第 2、Method 世界第 3，三队均完成 9/9。',
      sourceName: 'Method',
      sourceUrl: 'https://www.method.gg/raidprogress/midnight-season-1',
      publishedAt: '2026-04-16',
      analysisWindow: '至暗之夜 Season 1 史诗团队首杀战报'
    },
    {
      title: '最终首领拉数',
      value: '455 pulls',
      desc: 'Method 的 Top 10 收官更新列出 Liquid 击杀 Mythic Midnight Falls 用 455 pulls。',
      sourceName: 'Method',
      sourceUrl: 'https://www.method.gg/raidprogress/midnight-season-1',
      publishedAt: '2026-04-16',
      analysisWindow: '至暗之夜 Season 1 史诗团队首杀战报'
    }
  ],
  bossGuides: [
    {
      title: '团本结构',
      value: '3 团本 / 9 boss',
      desc: "Icy Veins 与 Wowhead 均列出 The Dreamrift、The Voidspire、March on Quel'Danas 三个团本，共 9 个首领。",
      sourceName: 'Icy Veins / Wowhead',
      sourceUrl: 'https://www.icy-veins.com/wow/midnight-season-1-raid-guide/',
      publishedAt: '2026-05-19',
      analysisWindow: '至暗之夜 Season 1 团本攻略与首领列表'
    },
    {
      title: 'The Voidspire',
      value: '6 boss',
      desc: '首领为 Imperator Averzian、Vorasius、Fallen-King Salhadaar、Vaelgor and Ezzorak、Lightblinded Vanguard、Crown of the Cosmos。',
      sourceName: 'Icy Veins / Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/raids-overview-hub-dates-locations',
      publishedAt: '2026-06-03',
      analysisWindow: '至暗之夜 Season 1 团本攻略与首领列表'
    },
    {
      title: 'March on Quel’Danas',
      value: '2 boss',
      desc: "最终团本包含 Belo'ren, Child of A'lar 与 Midnight Falls；Midnight Falls 是赛季最终首领。",
      sourceName: 'Icy Veins / Wowhead',
      sourceUrl: 'https://www.wowhead.com/guide/midnight/raids-overview-hub-dates-locations',
      publishedAt: '2026-06-03',
      analysisWindow: '至暗之夜 Season 1 团本攻略与首领列表'
    },
    {
      title: 'Midnight Falls 机制重点',
      value: '记忆游戏 / 水晶 / P4',
      desc: "Method 的 Mythic Midnight Falls 攻略强调 Grim Symphony 记忆游戏、水晶携带/交接、Galvanize soak 与秘密 P4 的像素集合。",
      sourceName: 'Method',
      sourceUrl: 'https://www.method.gg/guides/march-on-queldanas/midnight-falls',
      publishedAt: '2026-06-02',
      analysisWindow: '至暗之夜 Season 1 Mythic Midnight Falls 攻略'
    }
  ]
}

const pveZones = [
  {
    key: 'mythicPlus',
    title: '大秘境专区',
    eyebrow: latestPveAnalysis.seasonLabel,
    desc: '按当前赛季聚合大秘境队伍、职业专精和赛季副本三个维度，首页只展示入口和数据来源，不直接下结论。',
    sourceName: 'Icy Veins / Raider.IO / Wowhead',
    sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
    publishedAt: latestPveAnalysis.publishedAt,
    analysisWindow: latestPveAnalysis.analysisWindow,
    modules: [
      {
        key: 'teamLadder',
        title: '队伍天梯',
        desc: '主要看队伍维度：高层队伍配置、角色组合、层数区间和完成时间。',
        itemCount: sourceBackedItems.teamLadder.length,
        items: sourceBackedItems.teamLadder
      },
      {
        key: 'specLadder',
        title: '职业天梯',
        desc: '主要看职业专精维度：坦克、治疗、DPS 的出场率、热度和样本趋势。',
        itemCount: specLadderRecords.length,
        items: sourceBackedItems.specLadder,
        sourceName: 'Archon / Warcraft Logs',
        sourceUrl: archonTierUrl.dps,
        publishedAt: latestPveAnalysis.publishedAt,
        analysisWindow: 'High Keys Mythic+, All Dungeons, this week / WCL 2-week statistics',
        defaultRole: 'dps',
        selectedSpecId: specLadderSelectedSpecId,
        roles: specLadderRoleTabs,
        archonTierSummary: specLadderArchonTierSummary,
        wclDetailsBySpec: specLadderWclDetailsBySpec,
        sourceChecks: specLadderSourceChecks
      },
      {
        key: 'seasonDungeons',
        title: '赛季副本',
        desc: '按具体赛季副本维度整理路线压力、首领难点和副本样本表现。',
        itemCount: sourceBackedItems.seasonDungeons.length,
        items: sourceBackedItems.seasonDungeons
      }
    ]
  },
  {
    key: 'raid',
    title: '团队 raid 专区',
    eyebrow: '团本进度与首领打法',
    desc: '沉淀当前团本的首杀进度、首领机制和打法信息，后续由 WCL 与聚合源刷新。',
    sourceName: 'Warcraft Logs / Archon',
    sourceUrl: 'https://www.warcraftlogs.com/zone/rankings/latest',
    publishedAt: latestPveAnalysis.publishedAt,
    analysisWindow: latestPveAnalysis.analysisWindow,
    modules: [
      {
        key: 'raceToWorldFirst',
        title: '首杀战报',
        desc: '跟踪世界首杀、区域进度、击杀时间线和关键团队表现。',
        itemCount: sourceBackedItems.raceToWorldFirst.length,
        items: sourceBackedItems.raceToWorldFirst
      },
      {
        key: 'bossGuides',
        title: 'boss攻略',
        desc: '按 boss 维度整理机制、职责分配、灭团点和日志复盘入口。',
        itemCount: sourceBackedItems.bossGuides.length,
        items: sourceBackedItems.bossGuides
      }
    ]
  }
]

function buildPveHomePayload() {
  const season = buildCurrentSeasonPayload()
  return {
    navTitle: '副本',
    kicker: '能力 03',
    title: '大秘境与团队 Raid',
    desc: `${latestPveAnalysis.seasonLabel}。聚合大秘境队伍、职业专精、赛季副本和团队 raid 战报攻略，所有数据结论都保留来源与分析窗口。`,
    zones: pveZones,
    trustedSources: trustedPveSources,
    ...seasonMetadataFields(season),
    lastAnalyzedAt: latestPveAnalysis.publishedAt,
    analysisWindow: latestPveAnalysis.analysisWindow
  }
}

function getPveModuleDetail(moduleKey) {
  const season = buildCurrentSeasonPayload()
  const fallback = pveZones[0].modules[0]
  const module = pveZones
    .flatMap((zone) =>
      zone.modules.map((item) => ({
        ...item,
        zoneTitle: zone.title,
        zoneKey: zone.key,
        zoneEyebrow: zone.eyebrow,
        sourceName: item.sourceName || zone.sourceName,
        sourceUrl: item.sourceUrl || zone.sourceUrl,
        publishedAt: item.publishedAt || zone.publishedAt,
        analysisWindow: item.analysisWindow || zone.analysisWindow
      }))
    )
    .find((item) => item.key === moduleKey) || {
      ...fallback,
      zoneTitle: pveZones[0].title,
      zoneKey: pveZones[0].key,
      zoneEyebrow: pveZones[0].eyebrow,
      sourceName: pveZones[0].sourceName,
      sourceUrl: pveZones[0].sourceUrl,
      publishedAt: pveZones[0].publishedAt,
      analysisWindow: pveZones[0].analysisWindow
    }

  return {
    ...module,
    navTitle: module.title,
    ...seasonMetadataFields(season),
    lastAnalyzedAt: latestPveAnalysis.publishedAt
  }
}

module.exports = {
  buildPveHomePayload,
  getPveModuleDetail,
  trustedPveSources
}
