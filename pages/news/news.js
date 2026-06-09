Page({
  data: {
    navTitle: '资讯',
    kicker: '能力 01',
    title: '正式服与测试服资讯',
    desc: '追踪正式服、测试服的最新消息，聚合玩法改动、职业强度、版本热点和玩家关心的更新方向。',
    metrics: [
      { value: '18', label: '今日更新' },
      { value: '6', label: '职业变动' },
      { value: '3', label: '测试服重点' }
    ],
    quickActions: [
      { title: '正式服动态', desc: '版本公告、蓝贴与活动' },
      { title: '测试服前瞻', desc: 'PTR 改动与新内容' },
      { title: '玩法变化', desc: '系统、词缀和机制调整' },
      { title: '职业强度', desc: '热门专精趋势追踪' }
    ],
    tasks: [
      { title: '测试服职业平衡改动汇总', status: 'PTR', desc: '集中查看增减伤、天赋调整和关键技能变化。' },
      { title: '本周玩法热点', status: '正式服', desc: '整理新活动、装备获取和玩家高频讨论。' }
    ]
  }
})
