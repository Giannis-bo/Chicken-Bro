const { requestChickenbroMessage } = require('./simulator-api')
const { createChickenbroChatPage } = require('./chickenbro-chat')

Page(createChickenbroChatPage({
  navTitle: '炸鸡队长',
  showBack: true,
  kicker: '智能分析',
  pagePath: 'pages/simulator/chickenbro',
  source: 'simulator',
  requestChickenbroMessage
}))
