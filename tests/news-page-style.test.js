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

  assert.match(swiperBlock, /height:\s*408rpx;/)
  assert.match(bannerBlock, /height:\s*408rpx;/)
  assert.match(css, /\.news-swiper\s+\.wx-swiper-dots[\s\S]*bottom:\s*12rpx;/)
})
