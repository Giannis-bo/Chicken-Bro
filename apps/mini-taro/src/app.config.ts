export default defineAppConfig({
  pages: [
    'pages/chickenbro/index',
    'pages/simc/index',
    'pages/simc/tasks',
    'pages/simc/task-detail',
    'pages/auth/web-login-confirm',
  ],
  window: {
    backgroundColor: '#080908',
    backgroundTextStyle: 'light',
    navigationBarTextStyle: 'white',
    navigationBarBackgroundColor: '#121411',
    navigationStyle: 'default',
  },
  tabBar: {
    custom: true,
    color: '#766f61',
    selectedColor: '#e7b93d',
    backgroundColor: '#0e0c09',
    borderStyle: 'black',
    list: [
      { pagePath: 'pages/chickenbro/index', text: '队长' },
      { pagePath: 'pages/simc/index', text: 'SimC' },
    ],
  },
  style: 'v2',
  lazyCodeLoading: 'requiredComponents',
})
