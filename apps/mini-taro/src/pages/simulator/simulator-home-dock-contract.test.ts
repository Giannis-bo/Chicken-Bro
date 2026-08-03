import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Captain root dock spacing', () => {
  it('relies on the shell tab-bar reservation instead of adding a second bottom inset', () => {
    const composerStyle = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/ChickenbroChatComponents.module.scss',
    ), 'utf8')
    const routeStyle = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simulator-home.module.scss',
    ), 'utf8')

    expect(composerStyle).toMatch(/\.composer\s*\{[^}]*padding: 10px 14px 10px;/u)
    expect(composerStyle).not.toContain('env(safe-area-inset-bottom)')
    expect(routeStyle).not.toMatch(/\.transcriptRegion\s*\{[^}]*padding-bottom:/u)
  })

  it('keeps transcript scrolling inside the captain region with an explicit return-to-latest control', () => {
    const chatComponent = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/ChickenbroChatComponents.tsx',
    ), 'utf8')

    expect(chatComponent).toContain('<ScrollView')
    expect(chatComponent).toContain('data-role="chickenbro-transcript-scroll"')
    expect(chatComponent).toContain('data-role="chickenbro-return-latest"')
    expect(chatComponent).toContain('scrollTop={scrollTop}')
  })
})
