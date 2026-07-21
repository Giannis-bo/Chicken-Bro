import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function read(fileName: string): string {
  return readFileSync(resolve(process.cwd(), 'packages/design-system/src/components', fileName), 'utf8')
}

describe('builds home shared command components', () => {
  it('exposes stable class selector roles', () => {
    const source = read('BuildClassSelector.tsx')

    expect(source).toContain('data-role="build-class-selector"')
    expect(source).toContain('data-role="build-class-option"')
  })

  it('renders command cards without status or readiness copy', () => {
    const source = read('BuildCommandDeck.tsx')

    expect(source).toContain('data-role="build-command-card"')
    expect(source).not.toMatch(/stateLabel|statusLabel|准备状态/u)
  })

  it('exports both shared components and their contracts', () => {
    const source = readFileSync(resolve(process.cwd(), 'packages/design-system/src/index.ts'), 'utf8')

    expect(source).toContain("export { BuildClassSelector } from './components/BuildClassSelector'")
    expect(source).toContain("export type { BuildClassSelectorOption, BuildClassSelectorProps } from './components/BuildClassSelector'")
    expect(source).toContain("export { BuildCommandDeck } from './components/BuildCommandDeck'")
    expect(source).toContain("export type { BuildCommandDeckItem } from './components/BuildCommandDeck'")
  })
})
