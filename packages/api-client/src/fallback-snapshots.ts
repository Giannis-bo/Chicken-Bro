// Offline fallback fixtures. Transport state must always label them as stale or blocked.

import type {
  BuildsHomePayload,
  BuildsIntelPayload,
  NewsHomePayload,
} from '@wow-mini/domain'

export const newsFallbackSnapshot = {
  "navTitle": "最新资讯",
  "heroNews": [
    {
      "id": "blizzard-midnight-revelations-2026-06-03",
      "title": "Midnight: Revelations 内容更新将于 6 月 16 日上线",
      "summary": "官方公布 Midnight: Revelations 更新：新区域、全能典籍、单 Boss 团本 Sporefall、Turbulent Timeways 和后续故事章节。",
      "channel": "正式服动态",
      "category": "正式服",
      "tags": [
        "content-update",
        "raid"
      ],
      "importance": 100,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24266797/the-midnight-revelations-content-update-goes-live-17-june",
      "publishedAt": "2026-06-03",
      "sourceNote": "暴雪官方 World of Warcraft 新闻，页面标注 June 3rd by Blizzard Entertainment。",
      "bodyZh": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排。这次更新围绕新区域探索、全能典籍系统、单 Boss 团本 Sporefall、Turbulent Timeways 活动和后续故事章节展开，玩家可以提前了解更新上线后的主要游玩目标。\n\n对于正式服玩家来说，这类内容更新会影响近期的活动优先级、角色养成路线和团队副本准备节奏。详情页保留原文标题和来源链接，方便需要核对英文公告的玩家回到官方页面确认完整上下文。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排。这次更新围绕新区域探索、全能典籍系统、单 Boss 团本 Sporefall、Turbulent Timeways 活动和后续故事章节展开，玩家可以提前了解更新上线后的主要游玩目标。"
        },
        {
          "type": "paragraph",
          "text": "对于正式服玩家来说，这类内容更新会影响近期的活动优先级、角色养成路线和团队副本准备节奏。详情页保留原文标题和来源链接，方便需要核对英文公告的玩家回到官方页面确认完整上下文。"
        }
      ],
      "originalTitle": "The Midnight: Revelations Content Update Goes Live 17 June",
      "tagItems": [
        {
          "id": "content-update",
          "label": "内容更新"
        },
        {
          "id": "raid",
          "label": "团队副本"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24266797",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    },
    {
      "id": "blizzard-hotfixes-2026-06-03",
      "title": "官方热修更新至 2026 年 6 月 3 日",
      "summary": "官方热修列表更新，包含 Midnight 世界任务、职业套装和守护德鲁伊 Apex Talent 后续调整方向等修正说明。",
      "channel": "职业强度变化",
      "category": "正式服",
      "tags": [
        "hotfix",
        "class-change"
      ],
      "importance": 96,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
      "publishedAt": "2026-06-03",
      "sourceNote": "暴雪官方 Hotfixes 页面，标题更新为 Hotfixes: June 3, 2026。",
      "bodyZh": "中文正文：暴雪更新了官方热修列表，重点覆盖 Midnight 相关世界任务、职业套装效果和守护德鲁伊 Apex Talent 交互问题。热修通常会分批生效，一部分会在部署后立即生效，另一部分可能需要服务器重启或区域更新后才能体现。\n\n这类资讯适合关注正式服平衡和职业强度变化的玩家阅读。正文翻译保留调整范围和影响方向，但具体数值、技能名和后续追加条目仍建议通过底部来源按钮回到官方页面核对。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：暴雪更新了官方热修列表，重点覆盖 Midnight 相关世界任务、职业套装效果和守护德鲁伊 Apex Talent 交互问题。热修通常会分批生效，一部分会在部署后立即生效，另一部分可能需要服务器重启或区域更新后才能体现。"
        },
        {
          "type": "paragraph",
          "text": "这类资讯适合关注正式服平衡和职业强度变化的玩家阅读。正文翻译保留调整范围和影响方向，但具体数值、技能名和后续追加条目仍建议通过底部来源按钮回到官方页面核对。"
        }
      ],
      "originalTitle": "Hotfixes: June 3, 2026",
      "tagItems": [
        {
          "id": "hotfix",
          "label": "热修"
        },
        {
          "id": "class-change",
          "label": "职业调整"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24276957",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    },
    {
      "id": "blizzard-wow-weekly-2026-05-29",
      "title": "本周 WoW 汇总全能典籍、六月商栈与社区动态",
      "summary": "官方周报汇总本周重点内容，包含 Midnight 工具、六月商栈奖励、社区项目和后续资讯入口。",
      "channel": "正式服动态",
      "category": "正式服",
      "tags": [
        "weekly",
        "trading-post"
      ],
      "importance": 88,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24244887",
      "publishedAt": "2026-05-29",
      "sourceNote": "暴雪官方周报，页面标注 May 29, 2026 by Blizzard Entertainment。",
      "bodyZh": "中文正文：本周官方周报整理了近期《魔兽世界》的多个重点入口，包括 Midnight 相关工具说明、六月商栈奖励、社区项目和后续新闻链接。周报类内容适合玩家快速确认本周有哪些活动、系统更新和官方推荐阅读内容。\n\n这条资讯本身不是单一系统改动，而是一个官方导航页。详情页以中文整理核心信息，保留原文标题，方便玩家在需要进一步查看具体活动或公告时从底部来源按钮跳转到官方页面。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：本周官方周报整理了近期《魔兽世界》的多个重点入口，包括 Midnight 相关工具说明、六月商栈奖励、社区项目和后续新闻链接。周报类内容适合玩家快速确认本周有哪些活动、系统更新和官方推荐阅读内容。"
        },
        {
          "type": "paragraph",
          "text": "这条资讯本身不是单一系统改动，而是一个官方导航页。详情页以中文整理核心信息，保留原文标题，方便玩家在需要进一步查看具体活动或公告时从底部来源按钮跳转到官方页面。"
        }
      ],
      "originalTitle": "This Week in WoW",
      "tagItems": [
        {
          "id": "weekly",
          "label": "周报"
        },
        {
          "id": "trading-post",
          "label": "商栈"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24244887",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    }
  ],
  "metrics": [
    {
      "key": "today",
      "value": "4",
      "label": "今日更新"
    },
    {
      "key": "updates",
      "value": "2",
      "label": "更新"
    },
    {
      "key": "class-change",
      "value": "1",
      "label": "职业变动"
    },
    {
      "key": "events",
      "value": "3",
      "label": "活动"
    },
    {
      "key": "ptr",
      "value": "0",
      "label": "测试服重点"
    }
  ],
  "channels": [
    {
      "id": "retail",
      "title": "正式服动态",
      "desc": "官方公告、热修、活动与正式服版本内容",
      "updateCount": 3
    },
    {
      "id": "ptr",
      "title": "测试服前瞻",
      "desc": "PTR / Beta 改动、前瞻与开发说明",
      "updateCount": 0
    },
    {
      "id": "class",
      "title": "职业强度变化",
      "desc": "职业调优、套装修正与强度趋势",
      "updateCount": 1
    }
  ],
  "highlights": [
    {
      "id": "blizzard-midnight-revelations-2026-06-03",
      "title": "Midnight: Revelations 内容更新将于 6 月 16 日上线",
      "summary": "官方公布 Midnight: Revelations 更新：新区域、全能典籍、单 Boss 团本 Sporefall、Turbulent Timeways 和后续故事章节。",
      "channel": "正式服动态",
      "category": "正式服",
      "tags": [
        "content-update",
        "raid"
      ],
      "importance": 100,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24266797/the-midnight-revelations-content-update-goes-live-17-june",
      "publishedAt": "2026-06-03",
      "sourceNote": "暴雪官方 World of Warcraft 新闻，页面标注 June 3rd by Blizzard Entertainment。",
      "bodyZh": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排。这次更新围绕新区域探索、全能典籍系统、单 Boss 团本 Sporefall、Turbulent Timeways 活动和后续故事章节展开，玩家可以提前了解更新上线后的主要游玩目标。\n\n对于正式服玩家来说，这类内容更新会影响近期的活动优先级、角色养成路线和团队副本准备节奏。详情页保留原文标题和来源链接，方便需要核对英文公告的玩家回到官方页面确认完整上下文。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排。这次更新围绕新区域探索、全能典籍系统、单 Boss 团本 Sporefall、Turbulent Timeways 活动和后续故事章节展开，玩家可以提前了解更新上线后的主要游玩目标。"
        },
        {
          "type": "paragraph",
          "text": "对于正式服玩家来说，这类内容更新会影响近期的活动优先级、角色养成路线和团队副本准备节奏。详情页保留原文标题和来源链接，方便需要核对英文公告的玩家回到官方页面确认完整上下文。"
        }
      ],
      "originalTitle": "The Midnight: Revelations Content Update Goes Live 17 June",
      "tagItems": [
        {
          "id": "content-update",
          "label": "内容更新"
        },
        {
          "id": "raid",
          "label": "团队副本"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24266797",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    },
    {
      "id": "blizzard-hotfixes-2026-06-03",
      "title": "官方热修更新至 2026 年 6 月 3 日",
      "summary": "官方热修列表更新，包含 Midnight 世界任务、职业套装和守护德鲁伊 Apex Talent 后续调整方向等修正说明。",
      "channel": "职业强度变化",
      "category": "正式服",
      "tags": [
        "hotfix",
        "class-change"
      ],
      "importance": 96,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
      "publishedAt": "2026-06-03",
      "sourceNote": "暴雪官方 Hotfixes 页面，标题更新为 Hotfixes: June 3, 2026。",
      "bodyZh": "中文正文：暴雪更新了官方热修列表，重点覆盖 Midnight 相关世界任务、职业套装效果和守护德鲁伊 Apex Talent 交互问题。热修通常会分批生效，一部分会在部署后立即生效，另一部分可能需要服务器重启或区域更新后才能体现。\n\n这类资讯适合关注正式服平衡和职业强度变化的玩家阅读。正文翻译保留调整范围和影响方向，但具体数值、技能名和后续追加条目仍建议通过底部来源按钮回到官方页面核对。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：暴雪更新了官方热修列表，重点覆盖 Midnight 相关世界任务、职业套装效果和守护德鲁伊 Apex Talent 交互问题。热修通常会分批生效，一部分会在部署后立即生效，另一部分可能需要服务器重启或区域更新后才能体现。"
        },
        {
          "type": "paragraph",
          "text": "这类资讯适合关注正式服平衡和职业强度变化的玩家阅读。正文翻译保留调整范围和影响方向，但具体数值、技能名和后续追加条目仍建议通过底部来源按钮回到官方页面核对。"
        }
      ],
      "originalTitle": "Hotfixes: June 3, 2026",
      "tagItems": [
        {
          "id": "hotfix",
          "label": "热修"
        },
        {
          "id": "class-change",
          "label": "职业调整"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24276957",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    },
    {
      "id": "blizzard-wow-weekly-2026-05-29",
      "title": "本周 WoW 汇总全能典籍、六月商栈与社区动态",
      "summary": "官方周报汇总本周重点内容，包含 Midnight 工具、六月商栈奖励、社区项目和后续资讯入口。",
      "channel": "正式服动态",
      "category": "正式服",
      "tags": [
        "weekly",
        "trading-post"
      ],
      "importance": 88,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24244887",
      "publishedAt": "2026-05-29",
      "sourceNote": "暴雪官方周报，页面标注 May 29, 2026 by Blizzard Entertainment。",
      "bodyZh": "中文正文：本周官方周报整理了近期《魔兽世界》的多个重点入口，包括 Midnight 相关工具说明、六月商栈奖励、社区项目和后续新闻链接。周报类内容适合玩家快速确认本周有哪些活动、系统更新和官方推荐阅读内容。\n\n这条资讯本身不是单一系统改动，而是一个官方导航页。详情页以中文整理核心信息，保留原文标题，方便玩家在需要进一步查看具体活动或公告时从底部来源按钮跳转到官方页面。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：本周官方周报整理了近期《魔兽世界》的多个重点入口，包括 Midnight 相关工具说明、六月商栈奖励、社区项目和后续新闻链接。周报类内容适合玩家快速确认本周有哪些活动、系统更新和官方推荐阅读内容。"
        },
        {
          "type": "paragraph",
          "text": "这条资讯本身不是单一系统改动，而是一个官方导航页。详情页以中文整理核心信息，保留原文标题，方便玩家在需要进一步查看具体活动或公告时从底部来源按钮跳转到官方页面。"
        }
      ],
      "originalTitle": "This Week in WoW",
      "tagItems": [
        {
          "id": "weekly",
          "label": "周报"
        },
        {
          "id": "trading-post",
          "label": "商栈"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24244887",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    },
    {
      "id": "blizzard-june-trading-post-2026-05-28",
      "title": "六月商栈推出 An'she 主题奖励",
      "summary": "官方公布六月商栈物品与奖励，完成旅行者日志可获得焰绘太阳洛克坐骑。",
      "channel": "正式服动态",
      "category": "正式服",
      "tags": [
        "event",
        "trading-post",
        "rewards"
      ],
      "importance": 78,
      "sourceName": "Blizzard News",
      "sourceUrl": "https://news.blizzard.com/en-us/article/24271859/take-a-midsummer-stroll-over-to-the-june-trading-post",
      "publishedAt": "2026-05-28",
      "sourceNote": "暴雪官方新闻与论坛同步发布，论坛帖由 Blizzard Entertainment 于 2026-05-28 发布。",
      "bodyZh": "中文正文：暴雪公布了六月商栈轮换内容，本月主题围绕 An'she 风格奖励展开。玩家完成旅行者日志进度后，可以领取焰绘太阳洛克坐骑，同时也能在商栈中查看本月开放兑换的外观、坐骑和其他收藏物。\n\n商栈资讯主要影响收藏向玩家和想规划月度活动的玩家。中文正文保留奖励主题、获取方式和活动性质，具体物品清单、价格和图片仍以底部官方来源页面为准。",
      "bodyBlocksZh": [
        {
          "type": "paragraph",
          "text": "中文正文：暴雪公布了六月商栈轮换内容，本月主题围绕 An'she 风格奖励展开。玩家完成旅行者日志进度后，可以领取焰绘太阳洛克坐骑，同时也能在商栈中查看本月开放兑换的外观、坐骑和其他收藏物。"
        },
        {
          "type": "paragraph",
          "text": "商栈资讯主要影响收藏向玩家和想规划月度活动的玩家。中文正文保留奖励主题、获取方式和活动性质，具体物品清单、价格和图片仍以底部官方来源页面为准。"
        }
      ],
      "originalTitle": "Take a Midsummer Stroll Over to the June Trading Post",
      "tagItems": [
        {
          "id": "event",
          "label": "活动"
        },
        {
          "id": "trading-post",
          "label": "商栈"
        },
        {
          "id": "rewards",
          "label": "奖励"
        }
      ],
      "contentStatus": "ready",
      "translationStatus": "llm",
      "translationFidelity": "source_translation",
      "verificationStatus": "official_verified",
      "licenseStatus": "approved",
      "sourceTier": "official",
      "sourceBadges": [
        "官方已核验",
        "全文翻译"
      ],
      "canonicalTopicId": "news:24271859",
      "readingMeta": {
        "bodyBlockCount": 2,
        "estimatedReadingMinutes": 1
      }
    }
  ],
  "lastRefreshedAt": "2026-07-10T18:42:49.556Z",
  "refreshMode": "fallback"
} as unknown as NewsHomePayload

export const buildsHomeFallbackSnapshot = {
  "navTitle": "职业专精",
  "kicker": "职业控制台",
  "title": "职业专精",
  "desc": "追踪最高端大秘境、团本和 WCL 数据，首版先沉淀可直接参考的天赋与装备作业。",
  "quickActions": [
    {
      "key": "talents",
      "title": "天赋构筑",
      "desc": "按大秘境、团本和通用场景查看高端玩家常用天赋。",
      "phaseLabel": "输入",
      "actionLabel": "整理天赋",
      "scopeLabel": "天赋树",
      "evidenceLabel": "WebSim / 模板",
      "impactLabel": "决定构筑基础"
    },
    {
      "key": "gear",
      "title": "装备模拟",
      "desc": "替换装备、补齐 16 槽并保存装备配置字符串。",
      "phaseLabel": "输入",
      "actionLabel": "补齐装备",
      "scopeLabel": "16 槽装备",
      "evidenceLabel": "装备库 / 模板",
      "impactLabel": "决定 SimC 可提交性"
    },
    {
      "key": "simc",
      "title": "模拟 SimC",
      "desc": "组合已保存的天赋与装备模板，进入固定 SimC 工作台。",
      "phaseLabel": "验证",
      "actionLabel": "模拟校验",
      "scopeLabel": "固定模板",
      "evidenceLabel": "天赋 + 装备",
      "impactLabel": "生成可追踪任务"
    },
    {
      "key": "tasks",
      "title": "任务列表",
      "desc": "查看最近提交过的模拟任务，继续追踪结果。",
      "phaseLabel": "追踪",
      "actionLabel": "查看任务",
      "scopeLabel": "历史任务",
      "evidenceLabel": "SimC 结果",
      "impactLabel": "继续复盘行动"
    }
  ],
  "classOptions": [
    {
      "name": "死亡骑士",
      "websimClassKey": "deathknight",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg",
      "specializations": [
        {
          "id": "死亡骑士-鲜血",
          "className": "死亡骑士",
          "specName": "鲜血",
          "role": "坦克",
          "title": "鲜血死亡骑士",
          "status": "坦克",
          "classSlug": "death-knight",
          "specSlug": "blood",
          "websimClassKey": "deathknight",
          "websimSpecKey": "blood",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_bloodpresence.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_bloodpresence.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "死亡骑士-冰霜",
          "className": "死亡骑士",
          "specName": "冰霜",
          "role": "近战输出",
          "title": "冰霜死亡骑士",
          "status": "近战输出",
          "classSlug": "death-knight",
          "specSlug": "frost",
          "websimClassKey": "deathknight",
          "websimSpecKey": "frost",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "死亡骑士-邪恶",
          "className": "死亡骑士",
          "specName": "邪恶",
          "role": "近战输出",
          "title": "邪恶死亡骑士",
          "status": "近战输出",
          "classSlug": "death-knight",
          "specSlug": "unholy",
          "websimClassKey": "deathknight",
          "websimSpecKey": "unholy",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_unholypresence.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_unholypresence.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "恶魔猎手",
      "websimClassKey": "demonhunter",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter.jpg",
      "specializations": [
        {
          "id": "恶魔猎手-浩劫",
          "className": "恶魔猎手",
          "specName": "浩劫",
          "role": "近战输出",
          "title": "浩劫恶魔猎手",
          "status": "近战输出",
          "classSlug": "demon-hunter",
          "specSlug": "havoc",
          "websimClassKey": "demonhunter",
          "websimSpecKey": "havoc",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_specdps.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_specdps.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "恶魔猎手-复仇",
          "className": "恶魔猎手",
          "specName": "复仇",
          "role": "坦克",
          "title": "复仇恶魔猎手",
          "status": "坦克",
          "classSlug": "demon-hunter",
          "specSlug": "vengeance",
          "websimClassKey": "demonhunter",
          "websimSpecKey": "vengeance",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_spectank.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_spectank.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "恶魔猎手-噬灭",
          "className": "恶魔猎手",
          "specName": "噬灭",
          "role": "近战输出",
          "title": "噬灭恶魔猎手",
          "status": "近战输出",
          "classSlug": "demon-hunter",
          "specSlug": "devourer",
          "websimClassKey": "demonhunter",
          "websimSpecKey": "devourer",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter_void.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter_void.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "德鲁伊",
      "websimClassKey": "druid",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg",
      "specializations": [
        {
          "id": "德鲁伊-平衡",
          "className": "德鲁伊",
          "specName": "平衡",
          "role": "远程输出",
          "title": "平衡德鲁伊",
          "status": "远程输出",
          "classSlug": "druid",
          "specSlug": "balance",
          "websimClassKey": "druid",
          "websimSpecKey": "balance",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_starfall.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_starfall.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "德鲁伊-野性",
          "className": "德鲁伊",
          "specName": "野性",
          "role": "近战输出",
          "title": "野性德鲁伊",
          "status": "近战输出",
          "classSlug": "druid",
          "specSlug": "feral",
          "websimClassKey": "druid",
          "websimSpecKey": "feral",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_druid_catform.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_druid_catform.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "德鲁伊-守护",
          "className": "德鲁伊",
          "specName": "守护",
          "role": "坦克",
          "title": "守护德鲁伊",
          "status": "坦克",
          "classSlug": "druid",
          "specSlug": "guardian",
          "websimClassKey": "druid",
          "websimSpecKey": "guardian",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_racial_bearform.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_racial_bearform.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "德鲁伊-恢复",
          "className": "德鲁伊",
          "specName": "恢复",
          "role": "治疗",
          "title": "恢复德鲁伊",
          "status": "治疗",
          "classSlug": "druid",
          "specSlug": "restoration",
          "websimClassKey": "druid",
          "websimSpecKey": "restoration",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_druid.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_magicimmunity.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_magicimmunity.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "唤魔师",
      "websimClassKey": "evoker",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg",
      "specializations": [
        {
          "id": "唤魔师-湮灭",
          "className": "唤魔师",
          "specName": "湮灭",
          "role": "远程输出",
          "title": "湮灭唤魔师",
          "status": "远程输出",
          "classSlug": "evoker",
          "specSlug": "devastation",
          "websimClassKey": "evoker",
          "websimSpecKey": "devastation",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_devastation.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_devastation.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "唤魔师-恩护",
          "className": "唤魔师",
          "specName": "恩护",
          "role": "治疗",
          "title": "恩护唤魔师",
          "status": "治疗",
          "classSlug": "evoker",
          "specSlug": "preservation",
          "websimClassKey": "evoker",
          "websimSpecKey": "preservation",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_preservation.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_preservation.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "唤魔师-增辉",
          "className": "唤魔师",
          "specName": "增辉",
          "role": "辅助输出",
          "title": "增辉唤魔师",
          "status": "辅助输出",
          "classSlug": "evoker",
          "specSlug": "augmentation",
          "websimClassKey": "evoker",
          "websimSpecKey": "augmentation",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_augmentation.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_augmentation.jpg",
          "desc": "辅助输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "猎人",
      "websimClassKey": "hunter",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_hunter.jpg",
      "specializations": [
        {
          "id": "猎人-野兽控制",
          "className": "猎人",
          "specName": "野兽控制",
          "role": "远程输出",
          "title": "野兽控制猎人",
          "status": "远程输出",
          "classSlug": "hunter",
          "specSlug": "beast-mastery",
          "websimClassKey": "hunter",
          "websimSpecKey": "beast_mastery",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_hunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_bestialdiscipline.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_bestialdiscipline.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "猎人-射击",
          "className": "猎人",
          "specName": "射击",
          "role": "远程输出",
          "title": "射击猎人",
          "status": "远程输出",
          "classSlug": "hunter",
          "specSlug": "marksmanship",
          "websimClassKey": "hunter",
          "websimSpecKey": "marksmanship",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_hunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_focusedaim.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_focusedaim.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "猎人-生存",
          "className": "猎人",
          "specName": "生存",
          "role": "近战输出",
          "title": "生存猎人",
          "status": "近战输出",
          "classSlug": "hunter",
          "specSlug": "survival",
          "websimClassKey": "hunter",
          "websimSpecKey": "survival",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_hunter.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_camouflage.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_hunter_camouflage.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "法师",
      "websimClassKey": "mage",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg",
      "specializations": [
        {
          "id": "法师-奥术",
          "className": "法师",
          "specName": "奥术",
          "role": "远程输出",
          "title": "奥术法师",
          "status": "远程输出",
          "classSlug": "mage",
          "specSlug": "arcane",
          "websimClassKey": "mage",
          "websimSpecKey": "arcane",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_magicalsentry.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_magicalsentry.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "法师-火焰",
          "className": "法师",
          "specName": "火焰",
          "role": "远程输出",
          "title": "火焰法师",
          "status": "远程输出",
          "classSlug": "mage",
          "specSlug": "fire",
          "websimClassKey": "mage",
          "websimSpecKey": "fire",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_fire_firebolt02.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_fire_firebolt02.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "法师-冰霜",
          "className": "法师",
          "specName": "冰霜",
          "role": "远程输出",
          "title": "冰霜法师",
          "status": "远程输出",
          "classSlug": "mage",
          "specSlug": "frost",
          "websimClassKey": "mage",
          "websimSpecKey": "frost",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "武僧",
      "websimClassKey": "monk",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_monk.jpg",
      "specializations": [
        {
          "id": "武僧-酒仙",
          "className": "武僧",
          "specName": "酒仙",
          "role": "坦克",
          "title": "酒仙武僧",
          "status": "坦克",
          "classSlug": "monk",
          "specSlug": "brewmaster",
          "websimClassKey": "monk",
          "websimSpecKey": "brewmaster",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_monk.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_brewmaster_spec.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_brewmaster_spec.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "武僧-织雾",
          "className": "武僧",
          "specName": "织雾",
          "role": "治疗",
          "title": "织雾武僧",
          "status": "治疗",
          "classSlug": "monk",
          "specSlug": "mistweaver",
          "websimClassKey": "monk",
          "websimSpecKey": "mistweaver",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_monk.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_mistweaver_spec.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_mistweaver_spec.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "武僧-踏风",
          "className": "武僧",
          "specName": "踏风",
          "role": "近战输出",
          "title": "踏风武僧",
          "status": "近战输出",
          "classSlug": "monk",
          "specSlug": "windwalker",
          "websimClassKey": "monk",
          "websimSpecKey": "windwalker",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_monk.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_windwalker_spec.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_monk_windwalker_spec.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "圣骑士",
      "websimClassKey": "paladin",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg",
      "specializations": [
        {
          "id": "圣骑士-神圣",
          "className": "圣骑士",
          "specName": "神圣",
          "role": "治疗",
          "title": "神圣圣骑士",
          "status": "治疗",
          "classSlug": "paladin",
          "specSlug": "holy",
          "websimClassKey": "paladin",
          "websimSpecKey": "holy",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_holybolt.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_holybolt.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "圣骑士-防护",
          "className": "圣骑士",
          "specName": "防护",
          "role": "坦克",
          "title": "防护圣骑士",
          "status": "坦克",
          "classSlug": "paladin",
          "specSlug": "protection",
          "websimClassKey": "paladin",
          "websimSpecKey": "protection",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "圣骑士-惩戒",
          "className": "圣骑士",
          "specName": "惩戒",
          "role": "近战输出",
          "title": "惩戒圣骑士",
          "status": "近战输出",
          "classSlug": "paladin",
          "specSlug": "retribution",
          "websimClassKey": "paladin",
          "websimSpecKey": "retribution",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_auraoflight.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_auraoflight.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "牧师",
      "websimClassKey": "priest",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg",
      "specializations": [
        {
          "id": "牧师-戒律",
          "className": "牧师",
          "specName": "戒律",
          "role": "治疗",
          "title": "戒律牧师",
          "status": "治疗",
          "classSlug": "priest",
          "specSlug": "discipline",
          "websimClassKey": "priest",
          "websimSpecKey": "discipline",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_powerwordshield.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_powerwordshield.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "牧师-神圣",
          "className": "牧师",
          "specName": "神圣",
          "role": "治疗",
          "title": "神圣牧师",
          "status": "治疗",
          "classSlug": "priest",
          "specSlug": "holy",
          "websimClassKey": "priest",
          "websimSpecKey": "holy",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_holybolt.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_holybolt.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "牧师-暗影",
          "className": "牧师",
          "specName": "暗影",
          "role": "远程输出",
          "title": "暗影牧师",
          "status": "远程输出",
          "classSlug": "priest",
          "specSlug": "shadow",
          "websimClassKey": "priest",
          "websimSpecKey": "shadow",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_shadowwordpain.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_shadowwordpain.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "潜行者",
      "websimClassKey": "rogue",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_rogue.jpg",
      "specializations": [
        {
          "id": "潜行者-刺杀",
          "className": "潜行者",
          "specName": "刺杀",
          "role": "近战输出",
          "title": "刺杀潜行者",
          "status": "近战输出",
          "classSlug": "rogue",
          "specSlug": "assassination",
          "websimClassKey": "rogue",
          "websimSpecKey": "assassination",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_rogue.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_rogue_eviscerate.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_rogue_eviscerate.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "潜行者-狂徒",
          "className": "潜行者",
          "specName": "狂徒",
          "role": "近战输出",
          "title": "狂徒潜行者",
          "status": "近战输出",
          "classSlug": "rogue",
          "specSlug": "outlaw",
          "websimClassKey": "rogue",
          "websimSpecKey": "outlaw",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_rogue.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_rogue_waylay.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_rogue_waylay.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "潜行者-敏锐",
          "className": "潜行者",
          "specName": "敏锐",
          "role": "近战输出",
          "title": "敏锐潜行者",
          "status": "近战输出",
          "classSlug": "rogue",
          "specSlug": "subtlety",
          "websimClassKey": "rogue",
          "websimSpecKey": "subtlety",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_rogue.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_stealth.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_stealth.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "萨满祭司",
      "websimClassKey": "shaman",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_shaman.jpg",
      "specializations": [
        {
          "id": "萨满祭司-元素",
          "className": "萨满祭司",
          "specName": "元素",
          "role": "远程输出",
          "title": "元素萨满祭司",
          "status": "远程输出",
          "classSlug": "shaman",
          "specSlug": "elemental",
          "websimClassKey": "shaman",
          "websimSpecKey": "elemental",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_shaman.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_lightning.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_lightning.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "萨满祭司-增强",
          "className": "萨满祭司",
          "specName": "增强",
          "role": "近战输出",
          "title": "增强萨满祭司",
          "status": "近战输出",
          "classSlug": "shaman",
          "specSlug": "enhancement",
          "websimClassKey": "shaman",
          "websimSpecKey": "enhancement",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_shaman.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shaman_improvedstormstrike.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shaman_improvedstormstrike.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "萨满祭司-恢复",
          "className": "萨满祭司",
          "specName": "恢复",
          "role": "治疗",
          "title": "恢复萨满祭司",
          "status": "治疗",
          "classSlug": "shaman",
          "specSlug": "restoration",
          "websimClassKey": "shaman",
          "websimSpecKey": "restoration",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_shaman.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_magicimmunity.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_nature_magicimmunity.jpg",
          "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "术士",
      "websimClassKey": "warlock",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warlock.jpg",
      "specializations": [
        {
          "id": "术士-痛苦",
          "className": "术士",
          "specName": "痛苦",
          "role": "远程输出",
          "title": "痛苦术士",
          "status": "远程输出",
          "classSlug": "warlock",
          "specSlug": "affliction",
          "websimClassKey": "warlock",
          "websimSpecKey": "affliction",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warlock.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_deathcoil.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_deathcoil.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "术士-恶魔学识",
          "className": "术士",
          "specName": "恶魔学识",
          "role": "远程输出",
          "title": "恶魔学识术士",
          "status": "远程输出",
          "classSlug": "warlock",
          "specSlug": "demonology",
          "websimClassKey": "warlock",
          "websimSpecKey": "demonology",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warlock.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_metamorphosis.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_metamorphosis.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "术士-毁灭",
          "className": "术士",
          "specName": "毁灭",
          "role": "远程输出",
          "title": "毁灭术士",
          "status": "远程输出",
          "classSlug": "warlock",
          "specSlug": "destruction",
          "websimClassKey": "warlock",
          "websimSpecKey": "destruction",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warlock.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_rainoffire.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_shadow_rainoffire.jpg",
          "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    },
    {
      "name": "战士",
      "websimClassKey": "warrior",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warrior.jpg",
      "specializations": [
        {
          "id": "战士-武器",
          "className": "战士",
          "specName": "武器",
          "role": "近战输出",
          "title": "武器战士",
          "status": "近战输出",
          "classSlug": "warrior",
          "specSlug": "arms",
          "websimClassKey": "warrior",
          "websimSpecKey": "arms",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warrior.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_savageblow.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_savageblow.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "战士-狂怒",
          "className": "战士",
          "specName": "狂怒",
          "role": "近战输出",
          "title": "狂怒战士",
          "status": "近战输出",
          "classSlug": "warrior",
          "specSlug": "fury",
          "websimClassKey": "warrior",
          "websimSpecKey": "fury",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warrior.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_innerrage.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_innerrage.jpg",
          "desc": "近战输出专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        },
        {
          "id": "战士-防护",
          "className": "战士",
          "specName": "防护",
          "role": "坦克",
          "title": "防护战士",
          "status": "坦克",
          "classSlug": "warrior",
          "specSlug": "protection",
          "websimClassKey": "warrior",
          "websimSpecKey": "protection",
          "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_warrior.jpg",
          "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
          "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
          "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。",
          "sourceName": "Archon",
          "sourceUrl": "https://www.archon.gg/wow",
          "publishedAt": "2026-06-09",
          "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
          "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
        }
      ]
    }
  ],
  "featuredSpecializations": [],
  "trustedSources": [
    {
      "name": "Raider.IO",
      "url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
      "note": "高层大秘境队伍、角色分数、专精占比和路线样本。"
    },
    {
      "name": "Warcraft Logs",
      "url": "https://www.warcraftlogs.com/zone/rankings/latest",
      "note": "团本和大秘境日志、伤害构成、技能覆盖率和排名样本。"
    },
    {
      "name": "Archon",
      "url": "https://www.archon.gg/wow",
      "note": "基于 Warcraft Logs 的职业专精、天赋、装备和统计聚合。"
    },
    {
      "name": "Subcreation",
      "url": "https://www.subcreation.net/",
      "note": "大秘境与团本构筑聚合、专精趋势和装备热度。"
    }
  ],
  "lastAnalyzedAt": "2026-06-09",
  "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
  "currentSeason": {
    "id": "midnight-season-1",
    "seasonId": "midnight-season-1",
    "label": "至暗之夜 Season 1",
    "seasonLabel": "至暗之夜 Season 1",
    "revision": "season-midnight-season-1-c09b0948e307",
    "seasonRevision": "season-midnight-season-1-c09b0948e307",
    "verifiedAt": "2026-06-12T00:00:00+00:00",
    "expiresAt": "2026-06-13T00:00:00+00:00",
    "locale": "zh_CN",
    "dataStatus": "verified",
    "dungeons": [
      {
        "id": "magisters-terrace",
        "dungeonId": "magisters-terrace",
        "instanceId": "",
        "name": "Magisters' Terrace",
        "shortName": "Magisters' Terrace",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "maisara-caverns",
        "dungeonId": "maisara-caverns",
        "instanceId": "",
        "name": "Maisara Caverns",
        "shortName": "Maisara Caverns",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "nexus-point-xenas",
        "dungeonId": "nexus-point-xenas",
        "instanceId": "",
        "name": "Nexus-Point Xenas",
        "shortName": "Nexus-Point Xenas",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "windrunner-spire",
        "dungeonId": "windrunner-spire",
        "instanceId": "",
        "name": "Windrunner Spire",
        "shortName": "Windrunner Spire",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "algeth-ar-academy",
        "dungeonId": "algeth-ar-academy",
        "instanceId": "",
        "name": "Algeth'ar Academy",
        "shortName": "Algeth'ar Academy",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "pit-of-saron",
        "dungeonId": "pit-of-saron",
        "instanceId": "",
        "name": "Pit of Saron",
        "shortName": "Pit of Saron",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "seat-of-the-triumvirate",
        "dungeonId": "seat-of-the-triumvirate",
        "instanceId": "",
        "name": "Seat of the Triumvirate",
        "shortName": "Seat of the Triumvirate",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "skyreach",
        "dungeonId": "skyreach",
        "instanceId": "",
        "name": "Skyreach",
        "shortName": "Skyreach",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      }
    ],
    "raids": [
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "The Voidspire",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "The Dreamrift",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "March on Quel'Danas",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "Sporefall",
        "category": "Raid"
      }
    ],
    "sourceRefs": [
      {
        "name": "Blizzard News",
        "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
        "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
      },
      {
        "name": "Battle.net Game Data API",
        "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
        "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
      }
    ],
    "errors": []
  },
  "seasonId": "midnight-season-1",
  "seasonLabel": "至暗之夜 Season 1",
  "seasonRevision": "season-midnight-season-1-c09b0948e307",
  "verifiedAt": "2026-06-12T00:00:00+00:00",
  "expiresAt": "2026-06-13T00:00:00+00:00",
  "locale": "zh_CN",
  "dataStatus": "verified",
  "sourceRefs": [
    {
      "name": "Blizzard News",
      "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
      "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
    },
    {
      "name": "Battle.net Game Data API",
      "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
      "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
    }
  ]
} as unknown as BuildsHomePayload

export const buildsIntelFallbackSnapshot = {
  "navTitle": "热门专精",
  "title": "热门专精资讯",
  "desc": "展示当前已获取并保留来源证据的热门专精趋势，点击可进入对应专精的天赋构筑详情。",
  "count": 5,
  "items": [
    {
      "id": "法师-冰霜",
      "className": "法师",
      "specName": "冰霜",
      "role": "远程输出",
      "title": "冰霜法师",
      "status": "远程输出",
      "classSlug": "mage",
      "specSlug": "frost",
      "websimClassKey": "mage",
      "websimSpecKey": "frost",
      "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg",
      "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg",
      "desc": "远程输出专精，详情页首版聚焦天赋构筑和装备模拟。 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。",
      "sourceName": "Archon",
      "sourceUrl": "https://www.archon.gg/wow",
      "publishedAt": "2026-06-09",
      "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
      "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
    },
    {
      "id": "圣骑士-防护",
      "className": "圣骑士",
      "specName": "防护",
      "role": "坦克",
      "title": "防护圣骑士",
      "status": "坦克",
      "classSlug": "paladin",
      "specSlug": "protection",
      "websimClassKey": "paladin",
      "websimSpecKey": "protection",
      "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_paladin.jpg",
      "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/ability_warrior_defensivestance.jpg",
      "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。",
      "sourceName": "Archon",
      "sourceUrl": "https://www.archon.gg/wow",
      "publishedAt": "2026-06-09",
      "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
      "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
    },
    {
      "id": "唤魔师-增辉",
      "className": "唤魔师",
      "specName": "增辉",
      "role": "辅助输出",
      "title": "增辉唤魔师",
      "status": "辅助输出",
      "classSlug": "evoker",
      "specSlug": "augmentation",
      "websimClassKey": "evoker",
      "websimSpecKey": "augmentation",
      "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker.jpg",
      "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_augmentation.jpg",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_evoker_augmentation.jpg",
      "desc": "辅助输出专精，详情页首版聚焦天赋构筑和装备模拟。 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。",
      "sourceName": "Archon",
      "sourceUrl": "https://www.archon.gg/wow",
      "publishedAt": "2026-06-09",
      "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
      "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
    },
    {
      "id": "牧师-戒律",
      "className": "牧师",
      "specName": "戒律",
      "role": "治疗",
      "title": "戒律牧师",
      "status": "治疗",
      "classSlug": "priest",
      "specSlug": "discipline",
      "websimClassKey": "priest",
      "websimSpecKey": "discipline",
      "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_priest.jpg",
      "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_powerwordshield.jpg",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_holy_powerwordshield.jpg",
      "desc": "治疗专精，详情页首版聚焦天赋构筑和装备模拟。 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。",
      "sourceName": "Archon",
      "sourceUrl": "https://www.archon.gg/wow",
      "publishedAt": "2026-06-09",
      "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
      "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
    },
    {
      "id": "死亡骑士-鲜血",
      "className": "死亡骑士",
      "specName": "鲜血",
      "role": "坦克",
      "title": "鲜血死亡骑士",
      "status": "坦克",
      "classSlug": "death-knight",
      "specSlug": "blood",
      "websimClassKey": "deathknight",
      "websimSpecKey": "blood",
      "classIconUrl": "https://wow.zamimg.com/images/wow/icons/large/classicon_deathknight.jpg",
      "specIconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_bloodpresence.jpg",
      "iconUrl": "https://wow.zamimg.com/images/wow/icons/large/spell_deathknight_bloodpresence.jpg",
      "desc": "坦克专精，详情页首版聚焦天赋构筑和装备模拟。 已接入来源字段，适合作为资讯卡片展示最新构筑趋势。",
      "sourceName": "Archon",
      "sourceUrl": "https://www.archon.gg/wow",
      "publishedAt": "2026-06-09",
      "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
      "sourceNote": "由 Archon 聚合 Warcraft Logs 样本后用于职业专精趋势校验。"
    }
  ],
  "trustedSources": [
    {
      "name": "Raider.IO",
      "url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
      "note": "高层大秘境队伍、角色分数、专精占比和路线样本。"
    },
    {
      "name": "Warcraft Logs",
      "url": "https://www.warcraftlogs.com/zone/rankings/latest",
      "note": "团本和大秘境日志、伤害构成、技能覆盖率和排名样本。"
    },
    {
      "name": "Archon",
      "url": "https://www.archon.gg/wow",
      "note": "基于 Warcraft Logs 的职业专精、天赋、装备和统计聚合。"
    },
    {
      "name": "Subcreation",
      "url": "https://www.subcreation.net/",
      "note": "大秘境与团本构筑聚合、专精趋势和装备热度。"
    }
  ],
  "lastAnalyzedAt": "2026-06-09",
  "analysisWindow": "近 14 天高层大秘境、当前团本英雄/史诗日志与 WCL 排名样本",
  "currentSeason": {
    "id": "midnight-season-1",
    "seasonId": "midnight-season-1",
    "label": "至暗之夜 Season 1",
    "seasonLabel": "至暗之夜 Season 1",
    "revision": "season-midnight-season-1-c09b0948e307",
    "seasonRevision": "season-midnight-season-1-c09b0948e307",
    "verifiedAt": "2026-06-12T00:00:00+00:00",
    "expiresAt": "2026-06-13T00:00:00+00:00",
    "locale": "zh_CN",
    "dataStatus": "verified",
    "dungeons": [
      {
        "id": "magisters-terrace",
        "dungeonId": "magisters-terrace",
        "instanceId": "",
        "name": "Magisters' Terrace",
        "shortName": "Magisters' Terrace",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "maisara-caverns",
        "dungeonId": "maisara-caverns",
        "instanceId": "",
        "name": "Maisara Caverns",
        "shortName": "Maisara Caverns",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "nexus-point-xenas",
        "dungeonId": "nexus-point-xenas",
        "instanceId": "",
        "name": "Nexus-Point Xenas",
        "shortName": "Nexus-Point Xenas",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "windrunner-spire",
        "dungeonId": "windrunner-spire",
        "instanceId": "",
        "name": "Windrunner Spire",
        "shortName": "Windrunner Spire",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "algeth-ar-academy",
        "dungeonId": "algeth-ar-academy",
        "instanceId": "",
        "name": "Algeth'ar Academy",
        "shortName": "Algeth'ar Academy",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "pit-of-saron",
        "dungeonId": "pit-of-saron",
        "instanceId": "",
        "name": "Pit of Saron",
        "shortName": "Pit of Saron",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "seat-of-the-triumvirate",
        "dungeonId": "seat-of-the-triumvirate",
        "instanceId": "",
        "name": "Seat of the Triumvirate",
        "shortName": "Seat of the Triumvirate",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      },
      {
        "id": "skyreach",
        "dungeonId": "skyreach",
        "instanceId": "",
        "name": "Skyreach",
        "shortName": "Skyreach",
        "timerSeconds": 0,
        "sourceRefs": [
          {
            "name": "Blizzard News",
            "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
            "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
          },
          {
            "name": "Battle.net Game Data API",
            "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
            "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
          }
        ]
      }
    ],
    "raids": [
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "The Voidspire",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "The Dreamrift",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "March on Quel'Danas",
        "category": "Raid"
      },
      {
        "id": "",
        "raidId": "",
        "instanceId": "",
        "name": "Sporefall",
        "category": "Raid"
      }
    ],
    "sourceRefs": [
      {
        "name": "Blizzard News",
        "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
        "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
      },
      {
        "name": "Battle.net Game Data API",
        "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
        "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
      }
    ],
    "errors": []
  },
  "seasonId": "midnight-season-1",
  "seasonLabel": "至暗之夜 Season 1",
  "seasonRevision": "season-midnight-season-1-c09b0948e307",
  "verifiedAt": "2026-06-12T00:00:00+00:00",
  "expiresAt": "2026-06-13T00:00:00+00:00",
  "locale": "zh_CN",
  "dataStatus": "verified",
  "sourceRefs": [
    {
      "name": "Blizzard News",
      "url": "https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available",
      "note": "Official Midnight Season 1 Mythic+ dungeon rotation."
    },
    {
      "name": "Battle.net Game Data API",
      "url": "https://develop.battle.net/documentation/world-of-warcraft/game-data-apis",
      "note": "Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data."
    }
  ]
} as unknown as BuildsIntelPayload
