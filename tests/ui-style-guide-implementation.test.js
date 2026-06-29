const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(path) {
  return fs.readFileSync(path, 'utf8').toLowerCase().replace(/\r\n/g, '\n')
}

function block(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

test('global WXSS exposes the shared WoW mini-program design tokens', () => {
  const css = read('app.wxss')
  const tokens = [
    '--wow-bg',
    '--wow-panel',
    '--wow-panel-warm',
    '--wow-gold',
    '--wow-verified',
    '--wow-reference',
    '--wow-blocked',
    '--wow-stale'
  ]

  for (const token of tokens) {
    assert.match(css, new RegExp(`${token}:`), `${token} should be defined`)
  }

  const pageBlock = block(css, 'page')
  const heroBlock = block(css, '.hero')
  assert.match(pageBlock, /background:\s*#060606;[\s\S]*background:\s*var\(--wow-bg\);/)
  assert.match(pageBlock, /color:\s*#e1e2e5;[\s\S]*color:\s*var\(--wow-text\);/)
  assert.match(heroBlock, /border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.28\);[\s\S]*border:\s*1rpx solid var\(--wow-gold-border\);/)
  assert.match(heroBlock, /color:\s*#ffffff;[\s\S]*color:\s*var\(--wow-text-strong\);/)
  assert.match(heroBlock, /padding:\s*24rpx;/)
  assert.match(heroBlock, /border-radius:\s*12rpx;/)
  assert.match(block(css, '.section'), /padding:\s*20rpx;/)
  assert.match(block(css, '.section-header'), /gap:\s*16rpx;/)
})

test('top-level module heroes use black iron and gold as the dominant visual system', () => {
  const heroChecks = [
    ['pages/builds/builds.wxss', '.builds-hero', /#17120d/, /#8b3ff5\s+150%/],
    ['pages/pve/pve.wxss', '.pve-hero', /#17120d/, /#7a1116\s+0%/],
    ['pages/simulator/wcl.wxss', '.wcl-hero', /#17120d/, /#3a2a0b\s+0%/]
  ]

  for (const [file, selector, expected, oldDominant] of heroChecks) {
    const heroBlock = block(read(file), selector)
    assert.match(heroBlock, expected, `${selector} should use the shared warm panel base`)
    assert.doesNotMatch(heroBlock, oldDominant, `${selector} should keep class color as accent only`)
  }

  const simulatorChat = block(read('pages/simulator/simulator.wxss'), '.chickenbro-chat-shell')
  const chickenbroChat = block(read('pages/simulator/chickenbro.wxss'), '.chickenbro-chat-shell')
  assert.match(simulatorChat, /background:\s*#060606;/)
  assert.match(chickenbroChat, /background:\s*#060606;/)
  assert.match(block(read('pages/simulator/simulator.wxss'), '.chat-header-action'), /color:\s*#5bd6b4;/)
})

test('news and home module surfaces stay compact enough for mini-program first screens', () => {
  const newsCss = read('pages/news/news.wxss')
  assert.match(block(newsCss, '.news-swiper'), /height:\s*260rpx;/)
  assert.match(block(newsCss, '.banner-card'), /height:\s*260rpx;/)

  const buildsCss = read('pages/builds/builds.wxss')
  assert.match(block(buildsCss, '.query-card'), /min-height:\s*152rpx;/)

  const tasksCss = read('pages/simulator/tasks.wxss')
  assert.match(block(tasksCss, '.task-loading,\n.task-empty'), /padding:\s*24rpx;/)

  const pveCss = read('pages/pve/pve.wxss')
  assert.match(block(pveCss, '.zone-item'), /min-height:\s*136rpx;/)

  const simulatorCss = read('pages/simulator/simulator.wxss')
  assert.match(block(simulatorCss, '.chat-input-bar'), /position:\s*fixed;/)
  assert.match(block(simulatorCss, '.chat-bubble'), /max-width:\s*82%;/)
  assert.match(block(simulatorCss, '.chat-bubble'), /padding:\s*18rpx\s+20rpx;/)
})

test('primary form actions stay inside the compact 72rpx button rhythm', () => {
  const checks = [
    ['pages/simulator/simc.wxss', '.confirm-button,\n.submit-button'],
    ['pages/simulator/wcl.wxss', '.submit-button'],
    ['pages/simulator/chickenbro.wxss', '.send-button']
  ]

  for (const [file, selector] of checks) {
    const css = read(file)
    const buttonBlock = block(css, selector)
    assert.match(buttonBlock, /min-height:\s*72rpx;/, `${selector} in ${file} should be 72rpx high`)
    assert.doesNotMatch(buttonBlock, /line-height:\s*84rpx;/, `${selector} in ${file} should not keep 84rpx line height`)
  }
})

test('gear replacement sheet keeps apply action in the compact sheet rhythm', () => {
  const css = read('pages/builds/detail.wxss')
  const applyBlock = block(css, '.gear-apply-button')
  assert.match(applyBlock, /width:\s*100%;/)
  assert.match(applyBlock, /min-height:\s*64rpx;/)
  assert.match(applyBlock, /line-height:\s*64rpx;/)
  assert.doesNotMatch(applyBlock, /min-width:\s*156rpx;/)
  assert.doesNotMatch(applyBlock, /min-height:\s*72rpx;/)
})

test('gear replacement sheet keeps candidate detail action fixed and narrow', () => {
  const css = read('pages/builds/detail.wxss')
  const actionBlock = block(css, '.gear-candidate-action')
  const detailButtonBlock = block(css, '.gear-candidate-detail-button')
  assert.match(actionBlock, /width:\s*96rpx;/)
  assert.match(detailButtonBlock, /width:\s*86rpx;/)
  assert.match(detailButtonBlock, /min-height:\s*40rpx;/)
  assert.doesNotMatch(detailButtonBlock, /padding:\s*0\s+12rpx;/)
})
