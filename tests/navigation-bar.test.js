const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('navigation back icon follows the configured navigation text color', () => {
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')
  assert.match(css, /\.weui-navigation-bar__btn_goback[\s\S]*background-color:\s*currentColor/)
})

test('navigation home button has an implementation that returns to the news tab', () => {
  const js = fs.readFileSync('components/navigation-bar/navigation-bar.js', 'utf8')
  assert.match(js, /homePath:\s*{[\s\S]*value:\s*'\/pages\/news\/news'/)
  assert.match(js, /home\(\)\s*{[\s\S]*wx\.switchTab[\s\S]*this\.data\.homePath/)
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')
  assert.match(css, /\.weui-navigation-bar__btn_home[\s\S]*background-color:\s*currentColor/)
})
