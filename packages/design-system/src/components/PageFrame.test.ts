import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import * as pageFrameChrome from './PageFrame.chrome'
import { resolvePageChromeMode, type PageFrameVariant } from './PageFrame.chrome'

type PageFrameRightActionLayout = 'default' | 'builds-class-selector'

describe('resolvePageChromeMode', () => {
  it.each<PageFrameVariant>([
    'news-home',
    'builds-home',
    'simulator-home',
    'profile',
  ])('keeps the primary tab root %s on root chrome', (variant) => {
    expect(resolvePageChromeMode(variant)).toBe('root')
    expect(resolvePageChromeMode(variant, () => undefined)).toBe('root')
  })

  it('uses pushed chrome for routes with a back affordance', () => {
    expect(resolvePageChromeMode('workbench')).toBe('pushed')
    expect(resolvePageChromeMode('news-detail', () => undefined)).toBe('pushed')
    expect(resolvePageChromeMode('build-intel', () => undefined)).toBe('pushed-action')
    expect(resolvePageChromeMode('simc-submit', () => undefined)).toBe('pushed-action')
    expect(resolvePageChromeMode('chickenbro-chat', () => undefined)).toBe('chat')
  })

  it('does not manufacture back chrome for secondary content without a back handler', () => {
    expect(resolvePageChromeMode('news-detail')).toBe('root')
  })
})

describe('PageFrame right action layout', () => {
  const resolvePageFrameRightActionWidth = (
    pageFrameChrome as unknown as {
      resolvePageFrameRightActionWidth?: (layout: PageFrameRightActionLayout) => number
    }
  ).resolvePageFrameRightActionWidth

  it.each<[PageFrameRightActionLayout, number]>([
    ['default', 36],
    ['builds-class-selector', 120],
  ])('resolves the closed semantic layout %s to %i CSS px', (layout, width) => {
    expect(resolvePageFrameRightActionWidth).toBeTypeOf('function')
    expect(resolvePageFrameRightActionWidth?.(layout)).toBe(width)
  })

  it('binds the resolved width to the root header grid while preserving the default', () => {
    const pageFrameSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/PageFrame.tsx',
    ), 'utf8')
    const ownerStyleSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/owners.module.scss',
    ), 'utf8')

    expect(pageFrameSource).toContain("rightActionLayout = 'default'")
    expect(pageFrameSource).toContain('resolvePageFrameRightActionWidth(rightActionLayout)')
    expect(pageFrameSource).toContain("'--page-frame-right-action-width': `${rightActionWidth}px`")
    expect(pageFrameSource).toContain('data-right-action-layout={rightActionLayout}')
    expect(ownerStyleSource).toMatch(/\.pageFrame-root \.pageFrameHeader \{[\s\S]*?grid-template-columns:[^;]*var\(--page-frame-right-action-width, 36px\);/u)
  })
})
