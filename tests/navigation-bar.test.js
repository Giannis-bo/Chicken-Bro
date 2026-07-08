const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const { syncTabBarSelected } = require('../pages/common/tabbar-sync')

function readPngSize(file) {
  const buffer = fs.readFileSync(file)
  assert.equal(buffer.toString('ascii', 1, 4), 'PNG', `${file} should be a PNG`)
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  }
}

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

test('navigation shell does not render capture-only system chrome', () => {
  const js = fs.readFileSync('components/navigation-bar/navigation-bar.js', 'utf8')
  const wxml = fs.readFileSync('components/navigation-bar/navigation-bar.wxml', 'utf8')
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')

  assert.doesNotMatch(js, /showCaptureCapsule|captureClock/)
  assert.doesNotMatch(wxml, /showCaptureCapsule|capture-status|capture-capsule/)
  assert.doesNotMatch(css, /weui-navigation-bar__capture|capture-status|capture-capsule/)
})

test('navigation back and home buttons rely on one safe-area layer', () => {
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')
  const buttonRule = css.match(/\.weui-navigation-bar__buttons\s*\{([\s\S]*?)\n\}/)

  assert.ok(buttonRule, 'navigation button rule should exist')
  assert.doesNotMatch(buttonRule[1], /margin-top:\s*env\(safe-area-inset-top\)/)
})

test('navigation runtime status bar height is clamped instead of using safeArea.top', () => {
  const js = fs.readFileSync('components/navigation-bar/navigation-bar.js', 'utf8')
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')

  assert.match(js, /statusBarHeight/)
  assert.match(js, /clampStatusBarHeight/)
  assert.match(js, /Math\.min\(number,\s*64\)/)
  assert.doesNotMatch(js, /safeArea:\s*\{\s*top\s*=/)
  assert.doesNotMatch(js, /\$\{top\}px/)
  assert.match(js, /--status-bar-height:\s*\$\{statusBarHeight\}px/)
  assert.match(css, /--status-bar-height:\s*0px;/)
  assert.match(css, /height:\s*calc\(var\(--height\) \+ var\(--status-bar-height\)\)/)
  assert.match(css, /padding-top:\s*var\(--status-bar-height\)/)
  assert.doesNotMatch(css, /env\(safe-area-inset-top\)/)
})

test('navigation shell owns the app chrome layer above page materials', () => {
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')
  const rootRule = css.match(/\.weui-navigation-bar\s*\{([\s\S]*?)\n\}/)

  assert.ok(rootRule, 'navigation root rule should exist')
  assert.match(rootRule[1], /position:\s*relative;/)
  assert.match(rootRule[1], /z-index:\s*100;/)
  assert.match(rootRule[1], /isolation:\s*isolate;/)
  assert.match(rootRule[1], /contain:\s*layout paint style;/)
  assert.match(rootRule[1], /width:\s*100%;/)
  assert.match(rootRule[1], /max-width:\s*100vw;/)
  assert.match(rootRule[1], /box-sizing:\s*border-box;/)
})

test('navigation title treatment avoids a large black label box', () => {
  const css = fs.readFileSync('components/navigation-bar/navigation-bar.wxss', 'utf8')
  const titleHalo = css.match(/\.weui-navigation-bar__inner::after\s*\{([\s\S]*?)\n\}/)

  assert.ok(titleHalo, 'navigation title halo should be explicit')
  assert.match(titleHalo[1], /height:\s*2px/)
  assert.doesNotMatch(titleHalo[1], /height:\s*31px/)
  assert.doesNotMatch(titleHalo[1], /rgba\(6,\s*5,\s*4,\s*0\.46\)/)
})

test('pve tab is disabled for the first public version', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const pagePaths = app.tabBar.list.map((item) => item.pagePath)

  assert.ok(!pagePaths.includes('pages/pve/pve'))
  assert.ok(!app.pages.includes('pages/pve/pve'))
  assert.ok(!app.pages.includes('pages/pve/detail'))
})

test('simulator tab is renamed to smart analysis', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const tab = app.tabBar.list.find((item) => item.pagePath === 'pages/simulator/simulator')

  assert.equal(tab.text, '智能分析')
})

test('native tabBar icon assets are centered within the WeChat 81px contract', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const iconPaths = app.tabBar.list.flatMap((item) => [item.iconPath, item.selectedIconPath])

  assert.equal(iconPaths.length, 8)
  iconPaths.forEach((iconPath) => {
    assert.match(iconPath, /^assets\/tabbar\/.+\.png$/)
    const size = readPngSize(iconPath)
    assert.deepEqual(size, { width: 81, height: 81 }, `${iconPath} should not render as a stretched full tab image`)
  })
})

test('custom tabBar owns both icon and text rendering without startup expressions', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const wxml = fs.readFileSync('custom-tab-bar/index.wxml', 'utf8')
  const css = fs.readFileSync('custom-tab-bar/index.wxss', 'utf8')
  const js = fs.readFileSync('custom-tab-bar/index.js', 'utf8')

  assert.equal(app.tabBar.custom, true)
  app.tabBar.list.forEach((item) => {
    assert.match(item.iconPath, /^assets\/tabbar\/.+\.png$/)
    assert.match(item.selectedIconPath, /^assets\/tabbar\/.+\.png$/)
    assert.ok(item.text)
  })
  assert.match(wxml, /class="wow-tabbar"/)
  assert.match(wxml, /class="wow-tabbar__icon"/)
  assert.match(wxml, /class="wow-tabbar__glyph"/)
  assert.match(wxml, /class="wow-tabbar__label"/)
  assert.match(wxml, /<image[\s\S]*item\.currentIconPath/)
  assert.match(wxml, /binderror="handleIconError"/)
  assert.match(wxml, /item\.itemClass/)
  assert.match(wxml, /item\.iconLoadFailed/)
  assert.match(css, /grid-template-rows:\s*54rpx\s+32rpx;/)
  assert.match(css, /\.wow-tabbar__icon\s*\{[\s\S]*width:\s*38rpx;[\s\S]*height:\s*38rpx;/)
  assert.match(css, /\.wow-tabbar__glyph\s*\{[\s\S]*width:\s*38rpx;[\s\S]*height:\s*38rpx;[\s\S]*line-height:\s*38rpx;[\s\S]*text-align:\s*center;/)
  assert.match(css, /left:\s*0;/)
  assert.match(css, /right:\s*0;/)
  assert.match(css, /bottom:\s*0;/)
  assert.match(css, /height:\s*calc\(var\(--wow-tabbar-height-local\) \+ env\(safe-area-inset-bottom\)\);/)
  assert.match(css, /--wow-tabbar-height-local:\s*var\(--wow-tabbar-height,\s*132rpx\);/)
  assert.match(css, /border-radius:\s*0;/)
  assert.match(css, /z-index:\s*999;/)
  assert.match(js, /function emptyIconFailures\(\)/)
  assert.match(js, /function tabListForSelected\(selected,\s*iconFailures\)/)
  assert.match(js, /iconFailures:\s*emptyIconFailures\(\)/)
  assert.match(js, /currentIconPath:\s*active \? item\.selectedIconPath : item\.iconPath/)
  assert.match(js, /handleIconError\(event\)/)
  assert.match(js, /iconFailures\[index\]\s*=\s*true/)
  assert.match(js, /wx\.switchTab/)
  assert.match(js, /pageLifetimes:\s*{[\s\S]*show\(\)/)
})

test('tabBar page sync recomputes the custom list state instead of only changing selected', () => {
  let syncCount = 0
  let setDataPayload = null
  const page = {
    getTabBar() {
      return {
        data: { selected: 2 },
        setData(payload) {
          setDataPayload = payload
        },
        syncSelected() {
          syncCount += 1
        }
      }
    }
  }

  syncTabBarSelected(page, 3)

  assert.equal(syncCount, 1)
  assert.equal(setDataPayload, null)
})
