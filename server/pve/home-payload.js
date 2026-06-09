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
    {
      title: '惩戒圣骑士',
      value: '7.4%',
      desc: 'Icy Veins 的 Raider.IO 聚合显示，惩戒圣骑士是当周最热门专精。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    },
    {
      title: '冰霜法师',
      value: '7.1%',
      desc: '冰霜法师热度紧随惩戒之后，是当前最常见的大秘境输出专精之一。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    },
    {
      title: '酒仙武僧',
      value: '热门坦克',
      desc: '可读数据明确酒仙仍是当周最热门坦克，出现在高热度组合和高层样本的队伍维度中。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    },
    {
      title: '恶魔术士',
      value: '6.2%',
      desc: '恶魔术士是可读数据中第 3 个进入前列的 DPS 专精，并在队伍组合里持续出现。',
      sourceName: 'Icy Veins / Raider.IO',
      sourceUrl: 'https://www.icy-veins.com/wow/news/the-most-played-specs-and-groups-and-dps-logs-of-midnight-mythic-season-1/',
      publishedAt: '2026-06-07',
      analysisWindow: '至暗之夜 Season 1 第 3 周，本 reset 全层数大秘境样本'
    }
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
        itemCount: sourceBackedItems.specLadder.length,
        items: sourceBackedItems.specLadder
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
  return {
    navTitle: '副本',
    kicker: '能力 03',
    title: '大秘境与团队 Raid',
    desc: `${latestPveAnalysis.seasonLabel}。聚合大秘境队伍、职业专精、赛季副本和团队 raid 战报攻略，所有数据结论都保留来源与分析窗口。`,
    zones: pveZones,
    trustedSources: trustedPveSources,
    currentSeason: latestPveAnalysis.currentSeason,
    lastAnalyzedAt: latestPveAnalysis.publishedAt,
    analysisWindow: latestPveAnalysis.analysisWindow
  }
}

function getPveModuleDetail(moduleKey) {
  const fallback = pveZones[0].modules[0]
  const module = pveZones
    .flatMap((zone) =>
      zone.modules.map((item) => ({
        ...item,
        zoneTitle: zone.title,
        zoneKey: zone.key,
        zoneEyebrow: zone.eyebrow,
        sourceName: zone.sourceName,
        sourceUrl: zone.sourceUrl,
        publishedAt: zone.publishedAt,
        analysisWindow: zone.analysisWindow
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
    currentSeason: latestPveAnalysis.currentSeason,
    lastAnalyzedAt: latestPveAnalysis.publishedAt
  }
}

module.exports = {
  buildPveHomePayload,
  getPveModuleDetail,
  trustedPveSources
}
