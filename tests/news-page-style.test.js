const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function block(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

test('news carousel dots align with the banner card frame', () => {
  const css = fs.readFileSync('pages/news/news.wxss', 'utf8')
  const swiperBlock = block(css, '.news-swiper')
  const bannerBlock = block(css, '.banner-card')

  assert.match(swiperBlock, /height:\s*384rpx;/)
  assert.match(bannerBlock, /height:\s*384rpx;/)
  assert.match(css, /\.news-swiper\s+\.wx-swiper-dots[\s\S]*bottom:\s*12rpx;/)
})

test('news page adopts a dark Wowhead-style news surface', () => {
  const css = fs.readFileSync('pages/news/news.wxss', 'utf8')

  assert.match(css, /\.news-shell[\s\S]*background:\s*#060606;/)
  assert.match(css, /\.news-content[\s\S]*#060606[\s\S]*#101010/)
  assert.match(css, /\.banner-card[\s\S]*border-radius:\s*16rpx;/)
  assert.match(css, /\.banner-card[\s\S]*#f8b700/i)
  assert.match(css, /\.news-section[\s\S]*background:\s*#151515;/)
  assert.match(css, /\.highlight-card[\s\S]*background:\s*#101010;/)
  assert.doesNotMatch(css, /#fff7e5/i)
  assert.doesNotMatch(css, /#fffaf0/i)
})

test('news page does not expose manual refresh controls', () => {
  const js = fs.readFileSync('pages/news/news.js', 'utf8')
  const wxml = fs.readFileSync('pages/news/news.wxml', 'utf8')
  const css = fs.readFileSync('pages/news/news.wxss', 'utf8')
  const api = fs.readFileSync('pages/news/news-api.js', 'utf8')

  assert.doesNotMatch(js, /requestManualRefresh/)
  assert.doesNotMatch(js, /handleRefresh/)
  assert.doesNotMatch(js, /news_refresh/)
  assert.doesNotMatch(wxml, /bindtap="handleRefresh"/)
  assert.doesNotMatch(wxml, />刷新</)
  assert.doesNotMatch(css, /\.refresh-button/)
  assert.doesNotMatch(api, /requestManualRefresh/)
  assert.doesNotMatch(api, /mode=manual/)
})
