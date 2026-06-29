const { requestChickenbroMessage } = require('./simulator-api')
const { createChickenbroChatPage } = require('./chickenbro-chat')

Page(createChickenbroChatPage({
  navTitle: '智能分析',
  showBack: false,
  kicker: '智能分析',
  pagePath: 'pages/simulator/simulator',
  source: 'tab',
  requestChickenbroMessage
}))
