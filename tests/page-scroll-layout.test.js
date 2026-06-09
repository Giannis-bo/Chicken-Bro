const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function block(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

test('page scroll view has explicit flex height constraints for WeChat DevTools', () => {
  const css = fs.readFileSync('app.wxss', 'utf8')
  const pageBlock = block(css, 'page')
  const shellBlock = block(css, '.page-shell')
  const scrollBlock = block(css, '.page-scroll')

  assert.match(pageBlock, /height:\s*100vh;/)
  assert.match(shellBlock, /height:\s*100vh;/)
  assert.match(scrollBlock, /flex:\s*1;/)
  assert.match(scrollBlock, /min-height:\s*0;/)
  assert.match(scrollBlock, /height:\s*0;/)
  assert.doesNotMatch(scrollBlock, /overflow-y:\s*hidden;/)
})
