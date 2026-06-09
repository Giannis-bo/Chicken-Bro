Page({
  data: {
    navTitle: '模拟器',
    kicker: '能力 04',
    title: '构筑模拟器与 AI 分析',
    desc: '提供 AI 辅助能力，帮助玩家跑 SimCraft、分析 WCL 数据、比较配装收益和定位输出问题。',
    metrics: [
      { value: 'AI', label: '辅助分析' },
      { value: 'Sim', label: 'SimCraft' },
      { value: 'WCL', label: '日志复盘' }
    ],
    quickActions: [
      { title: '跑 SimCraft', desc: '比较装备、天赋和属性收益' },
      { title: '分析 WCL', desc: '定位循环、爆发和减员问题' },
      { title: '配装对比', desc: '多套装备收益横向比较' },
      { title: 'AI 建议', desc: '生成可执行优化建议' }
    ],
    tasks: [
      { title: '导入角色构筑', status: '待接入', desc: '后续可粘贴角色数据，生成 SimCraft 配置。' },
      { title: 'WCL 战斗日志分析', status: '高级', desc: '用 AI 总结输出差距、技能覆盖和关键失误。' }
    ]
  }
})
