export default defineAppConfig({
  pages: [
    'pages/web/index',
  ],
  window: {
    backgroundColor: '#faf8f5',
    backgroundTextStyle: 'dark',
    navigationBarTextStyle: 'black',
    navigationBarBackgroundColor: '#faf8f5',
    navigationStyle: 'default',
  },
  style: 'v2',
  lazyCodeLoading: 'requiredComponents',
})
