export default defineAppConfig({
  pages: [
    'pages/chickenbro/index',
    'pages/simc/index',
    'pages/simc/tasks',
    'pages/simc/task-detail',
    'pages/auth/web-login-confirm',
  ],
  window: {
    backgroundColor: '#faf8f5',
    backgroundTextStyle: 'dark',
    navigationBarTextStyle: 'black',
    navigationBarBackgroundColor: '#faf8f5',
    navigationStyle: 'default',
  },
  tabBar: {
    custom: true,
    color: '#766f61',
    selectedColor: '#9e5145',
    backgroundColor: '#faf8f5',
    borderStyle: 'white',
    list: [
      { pagePath: 'pages/chickenbro/index', text: '聊天' },
      { pagePath: 'pages/simc/index', text: 'Simc模拟' },
    ],
  },
  style: 'v2',
  lazyCodeLoading: 'requiredComponents',
})
