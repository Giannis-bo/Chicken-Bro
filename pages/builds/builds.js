Page({
  data: {
    navTitle: 'BD',
    kicker: '能力 02',
    title: '职业专精 BD 查询',
    desc: '按职业和专精查询天赋搭配、属性权重、毕业装备、饰品选择和常用输出循环。',
    metrics: [
      { value: '13', label: '职业' },
      { value: '39', label: '职业专精' },
      { value: '120+', label: '装备方案' }
    ],
    quickActions: [
      { title: '天赋搭配', desc: '团本、大秘境场景区分' },
      { title: '毕业装备', desc: 'BIS、饰品和套装选择' },
      { title: '属性优先级', desc: '主副属性与阈值参考' },
      { title: '输出手法', desc: '起手、爆发和循环' }
    ],
    tasks: [
      { title: '冰法大秘境 BD', status: '热门', desc: '查看天赋代码、核心橙装思路和饰品搭配建议。' },
      { title: '防战团本配装', status: '团本', desc: '对比生存向、输出向和通用向毕业装备。' }
    ]
  }
})
