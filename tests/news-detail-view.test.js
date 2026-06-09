const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('news detail page renders Chinese body and original text sections', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')

  assert.match(wxml, /article\.bodyZh/)
  assert.match(wxml, /原文/)
  assert.match(wxml, /article\.originalTitle/)
  assert.match(wxml, /article\.originalBody/)
})

test('news detail tags use compact chips instead of large metadata cards', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/news/detail.wxss', 'utf8')

  assert.doesNotMatch(wxml, /detail-info-grid/)
  assert.doesNotMatch(wxml, /资讯 ID/)
  assert.doesNotMatch(wxml, /重要度/)
  assert.match(css, /\.detail-chip[\s\S]*font-size:\s*(18|19|20)rpx/)
})

test('news detail clears loading even when the detail request rejects', () => {
  const js = fs.readFileSync('pages/news/detail.js', 'utf8')

  assert.match(js, /requestArticleDetail\(articleId\)[\s\S]*\.catch\(/)
  assert.match(js, /\.finally\(\(\)\s*=>\s*{[\s\S]*loading:\s*false/)
})
