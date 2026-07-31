'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const {
  assertAutomatorRuntimeCompatible,
  assertExpectedProject,
  connectAutomatorEndpoint,
  expectedAppId,
  findElementBySemanticValue,
  hasRenderedRoot,
  queryElementsByXpathSequentially,
  queryElementsWithXpathFallback,
  readSemanticValue,
  scrollElementIntoView,
  scrollPageElementIntoView,
  waitForSystemInfo,
} = require('../scripts/wechat-automator')

test('connectAutomatorEndpoint bypasses the broken DevTools Tool.getInfo SDKVersion shape', async () => {
  const calls = []
  const miniProgram = {
    callWxMethod: async (method) => {
      calls.push(method)
      return { SDKVersion: '3.16.2' }
    },
  }
  const connectTool = async ({ wsEndpoint }) => {
    assert.equal(wsEndpoint, 'ws://127.0.0.1:9420')
    return miniProgram
  }

  assert.equal(
    await connectAutomatorEndpoint('ws://127.0.0.1:9420', connectTool),
    miniProgram,
  )
  assert.deepEqual(calls, ['getSystemInfoSync'])
})

test('connectAutomatorEndpoint honors the caller runtime compatibility deadline', async () => {
  const miniProgram = {
    callWxMethod: async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
      return { SDKVersion: '3.16.2' }
    },
    disconnect() {},
  }

  await assert.rejects(
    connectAutomatorEndpoint(
      'ws://127.0.0.1:9420',
      async () => miniProgram,
      1,
    ),
    /timed out after 1ms/u,
  )
})

test('assertAutomatorRuntimeCompatible fails closed when the real runtime SDK is missing', async () => {
  const miniProgram = {
    callWxMethod: async () => ({ version: '2.02.2607161' }),
  }
  await assert.rejects(
    assertAutomatorRuntimeCompatible(miniProgram),
    /runtime SDKVersion is missing/u,
  )
})

test('assertAutomatorRuntimeCompatible rejects an obsolete real runtime SDK', async () => {
  const miniProgram = {
    callWxMethod: async () => ({ SDKVersion: '2.6.9' }),
  }
  await assert.rejects(
    assertAutomatorRuntimeCompatible(miniProgram),
    /requires at least 2.7.3/u,
  )
})

test('assertAutomatorRuntimeCompatible rejects a malformed real runtime SDK', async () => {
  const miniProgram = {
    callWxMethod: async () => ({ SDKVersion: 'current' }),
  }
  await assert.rejects(
    assertAutomatorRuntimeCompatible(miniProgram),
    /runtime SDKVersion is invalid/u,
  )
})

test('assertExpectedProject accepts only the configured wow mini program', async () => {
  const accountInfo = { miniProgram: { appId: expectedAppId } }
  const miniProgram = {
    callWxMethod: async (method) => {
      assert.equal(method, 'getAccountInfoSync')
      return accountInfo
    },
  }
  assert.equal(await assertExpectedProject(miniProgram), accountInfo)
})

test('assertExpectedProject rejects an automation endpoint for another project', async () => {
  const miniProgram = {
    callWxMethod: async () => ({ miniProgram: { appId: 'wx-another-project' } }),
  }
  await assert.rejects(
    assertExpectedProject(miniProgram),
    new RegExp(`expected ${expectedAppId}$`, 'u'),
  )
})

test('hasRenderedRoot rejects the transient empty Taro root', () => {
  assert.equal(hasRenderedRoot({ root: { cn: [] } }), false)
  assert.equal(hasRenderedRoot({ root: { cn: [{ type: 'view' }] } }), true)
})

test('readSemanticValue prefers a rendered data attribute', async () => {
  const element = {
    attribute: async (name) => name === 'data-selected' ? 'true' : 'wx-data-selected-false',
  }
  assert.equal(await readSemanticValue(element, 'selected'), 'true')
})

test('readSemanticValue falls back to the WeChat selector marker class', async () => {
  const element = {
    attribute: async (name) => name === 'class'
      ? 'control wx-data-material-owner-css wx-data-leading-boundary-active'
      : null,
  }
  assert.equal(await readSemanticValue(element, 'material-owner'), 'css')
  assert.equal(await readSemanticValue(element, 'data-leading-boundary'), 'active')
})

test('queryElementsWithXpathFallback prefers ordinary semantic selectors', async () => {
  const element = { id: 'css-element' }
  let xpathCalls = 0
  const page = {
    $$: async (selector) => {
      assert.equal(selector, '.wx-data-role-gear-candidate-variant')
      return [element]
    },
    getElementByXpath: async () => {
      xpathCalls += 1
      return { id: 'xpath-element' }
    },
  }

  assert.deepEqual(await queryElementsWithXpathFallback(
    page,
    '.wx-data-role-gear-candidate-variant',
    '//*[contains(@class, "gear-candidate-variant")]',
  ), [element])
  assert.equal(xpathCalls, 0)
})

test('queryElementsWithXpathFallback recovers a rendered DevTools control omitted by CSS lookup', async () => {
  const element = { id: 'xpath-element' }
  const xpath = '//*[contains(@class, "gear-candidate-variant")]'
  const page = {
    $$: async () => [],
    getElementByXpath: async (actual) => {
      assert.equal(actual, xpath)
      return element
    },
  }

  assert.deepEqual(await queryElementsWithXpathFallback(
    page,
    '.wx-data-role-gear-candidate-variant',
    xpath,
  ), [element])
})

test('queryElementsByXpathSequentially enumerates every rendered element until the first gap', async () => {
  const calls = []
  const element = (id) => ({
    id,
    attribute: async (name) => name === 'class' ? `rendered-${id}` : null,
  })
  const page = {
    getElementByXpath: async (xpath) => {
      calls.push(xpath)
      if (xpath.endsWith('[1]')) return element('one')
      if (xpath.endsWith('[2]')) return element('two')
      return null
    },
  }

  assert.deepEqual(
    (await queryElementsByXpathSequentially(
      page,
      '//*[contains(@class, "gear-candidate-variant")]',
      4,
    )).map((item) => item.id),
    ['one', 'two'],
  )
  assert.deepEqual(calls, [
    '(//*[contains(@class, "gear-candidate-variant")])[1]',
    '(//*[contains(@class, "gear-candidate-variant")])[2]',
    '(//*[contains(@class, "gear-candidate-variant")])[3]',
  ])
})

test('queryElementsByXpathSequentially fails closed at its element cap', async () => {
  const page = {
    getElementByXpath: async () => ({
      id: 'still-present',
      attribute: async () => 'rendered',
    }),
  }

  await assert.rejects(
    queryElementsByXpathSequentially(page, '//*[contains(@class, "variant")]', 2),
    /xpath element cap exceeded/u,
  )
})

test('queryElementsByXpathSequentially treats the current DevTools phantom wrapper as a missing element', async () => {
  const page = {
    getElementByXpath: async (xpath) => xpath.endsWith('[1]')
      ? { attribute: async () => 'rendered' }
      : {
          attribute: async () => {
            throw new Error("Cannot read properties of undefined (reading 'attributes')")
          },
        },
  }

  assert.equal(
    (await queryElementsByXpathSequentially(page, '//*[contains(@class, "variant")]', 3)).length,
    1,
  )
})

test('findElementBySemanticValue locates a long rendered identity without a CSS value selector', async () => {
  const longVariantKey = (
    'browse-variant-sha256-'
    + '809f88c0a861d315ab7fb993257b29e78e8256c9dfa5fe278cffdeda600a55cb'
  )
  const element = (key) => ({
    key,
    attribute: async (name) => {
      if (name === 'data-variant-key') return null
      if (name === 'class') {
        return (
          'wx-data-role-gear-candidate-variant '
          + `wx-data-variant-key-${key}`
        )
      }
      return null
    },
  })
  const values = [element('another-variant'), element(longVariantKey)]
  const page = {
    getElementByXpath: async (xpath) => {
      const match = xpath.match(/\[(\d+)\]$/u)
      return match ? values[Number(match[1]) - 1] ?? null : null
    },
  }

  assert.equal(
    await findElementBySemanticValue(
      page,
      '//*[contains(@class, "wx-data-role-gear-candidate-variant")]',
      32,
      'variant-key',
      longVariantKey,
    ),
    values[1],
  )
})

test('findElementBySemanticValue queries the exact semantic class before enumerating XPath siblings', async () => {
  const longVariantKey = (
    'browse-variant-sha256-'
    + '0427c68800674547f1848a0fcbc55a9ee9237e764cb032e1082e9a9f40caa6c1'
  )
  const target = {
    attribute: async (name) => {
      if (name === 'data-variant-key') return null
      if (name === 'class') {
        return (
          'wx-data-role-gear-candidate-variant '
          + `wx-data-variant-key-${longVariantKey}`
        )
      }
      return null
    },
  }
  const page = {
    getElementByXpath: async (xpath) => {
      assert.equal(
        xpath,
        `//*[contains(@class, "wx-data-variant-key-${longVariantKey}")]`,
      )
      return target
    },
  }

  assert.equal(
    await findElementBySemanticValue(
      page,
      '//*[contains(@class, "wx-data-role-gear-candidate-variant")]',
      32,
      'variant-key',
      longVariantKey,
    ),
    target,
  )
})

test('scrollElementIntoView scrolls a lower sheet control into the visible viewport', async () => {
  const calls = []
  const scrollView = {
    offset: async () => ({ left: 0, top: 100 }),
    size: async () => ({ width: 390, height: 400 }),
    property: async (name) => name === 'scrollTop' ? 240 : null,
    scrollTo: async (x, y) => calls.push([x, y]),
  }
  const element = {
    offset: async () => ({ left: 20, top: 540 }),
    size: async () => ({ width: 350, height: 80 }),
  }

  assert.equal(
    await scrollElementIntoView(scrollView, element, 'third variant'),
    true,
  )
  assert.deepEqual(calls, [[0, 376]])
})

test('scrollElementIntoView leaves an already visible control in place', async () => {
  const calls = []
  const scrollView = {
    offset: async () => ({ left: 0, top: 100 }),
    size: async () => ({ width: 390, height: 400 }),
    property: async (name) => name === 'scrollTop' ? 240 : null,
    scrollTo: async (x, y) => calls.push([x, y]),
  }
  const element = {
    offset: async () => ({ left: 20, top: 180 }),
    size: async () => ({ width: 350, height: 80 }),
  }

  assert.equal(
    await scrollElementIntoView(scrollView, element, 'visible variant'),
    false,
  )
  assert.deepEqual(calls, [])
})

test('scrollPageElementIntoView uses the real page scroll API before an offscreen tap', async () => {
  const calls = []
  const miniProgram = {
    callWxMethod: async (method, value) => calls.push([method, value]),
  }
  const page = {
    scrollTop: async () => 300,
  }
  const element = {
    offset: async () => ({ left: 20, top: 820 }),
    size: async () => ({ width: 350, height: 100 }),
  }

  assert.equal(
    await scrollPageElementIntoView(miniProgram, page, element, 844, 'back slot'),
    true,
  )
  assert.deepEqual(calls, [[
    'pageScrollTo',
    { scrollTop: 392, duration: 0 },
  ]])
})

test('waitForSystemInfo tolerates the build handoff before the WeChat runtime responds', async () => {
  let calls = 0
  const miniProgram = {
    systemInfo: async () => {
      calls += 1
      if (calls === 1) throw new Error('runtime compiling')
      return { windowWidth: 390, windowHeight: 844, pixelRatio: 3 }
    },
  }
  assert.deepEqual(await waitForSystemInfo(miniProgram), {
    windowWidth: 390,
    windowHeight: 844,
    pixelRatio: 3,
  })
  assert.equal(calls, 2)
})
