const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('news detail page renders translated body with original title but without original body', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')

  assert.match(wxml, /article\.bodyBlocksZh/)
  assert.match(wxml, /原题：/)
  assert.match(wxml, /article\.originalTitle/)
  assert.match(wxml, /wx:if="\{\{article\.originalTitle\}\}" class="detail-original-title"/)
  assert.doesNotMatch(wxml, /article\.originalBody/)
  assert.doesNotMatch(wxml, /original-panel/)
})

test('news detail renders Chinese tag chips and a compact source footer', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/news/detail.wxss', 'utf8')

  assert.doesNotMatch(wxml, /detail-info-grid/)
  assert.doesNotMatch(wxml, /资讯 ID/)
  assert.doesNotMatch(wxml, /重要度/)
  assert.match(wxml, /article\.tagItems/)
  assert.doesNotMatch(wxml, /source-url/)
  assert.match(wxml, /source-footer/)
  assert.match(wxml, /复制来源链接/)
  assert.match(css, /\.detail-chip[\s\S]*font-size:\s*(18|19|20)rpx/)
  assert.match(css, /\.source-button[\s\S]*height:\s*(44|46|48)rpx/)
})

test('news detail renders source trust badges and body block styles for mobile reading', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/news/detail.wxss', 'utf8')

  assert.match(wxml, /article\.sourceBadges/)
  assert.match(wxml, /body-block-heading/)
  assert.match(wxml, /body-block-list/)
  assert.match(wxml, /body-block-quote/)
  assert.match(css, /\.body-block-paragraph[\s\S]*font-size:\s*(27|28|29)rpx/)
  assert.match(css, /\.body-block-paragraph[\s\S]*line-height:\s*1\.(6[5-9]|7[0-5])/)
})

test('news detail labels the published date instead of showing a bare date', () => {
  const wxml = fs.readFileSync('pages/news/detail.wxml', 'utf8')

  assert.match(wxml, /发布时间/)
  assert.doesNotMatch(wxml, /<text class="detail-date">\{\{article\.publishedAt\}\}<\/text>/)
})

test('news detail clears loading even when the detail request rejects', () => {
  const js = fs.readFileSync('pages/news/detail.js', 'utf8')

  assert.match(js, /requestArticleDetail\(articleId\)[\s\S]*\.catch\(/)
  assert.match(js, /\.finally\(\(\)\s*=>\s*{[\s\S]*loading:\s*false/)
})

test('news detail does not treat summary as a complete translated body', () => {
  const js = fs.readFileSync('pages/news/detail.js', 'utf8')

  assert.doesNotMatch(js, /bodyZh\s*=\s*article\.bodyZh\s*\|\|\s*article\.summary/)
  assert.match(js, /tagItems/)
})
