import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/components', () => ({
  Button: 'button',
  Image: 'image',
  Text: 'text',
  View: 'view',
}))

import {
  activateBuildClassOption,
  resolveBuildClassSelection,
  type BuildClassSelectorOption,
} from './BuildClassSelector'
import {
  activateBuildCommand,
  buildCommandDeckEntries,
  type BuildCommandDeckItem,
} from './BuildCommandDeck'

function read(fileName: string): string {
  return readFileSync(resolve(process.cwd(), 'packages/design-system/src/components', fileName), 'utf8')
}

const classOptions: readonly BuildClassSelectorOption[] = [
  { id: 'mage', label: '法师', disabled: false, selected: true },
  { id: 'warrior', label: '战士', disabled: false, selected: true },
  { id: 'monk', label: '武僧', disabled: true, selected: false },
]

const commandItems: readonly BuildCommandDeckItem[] = [
  {
    id: 'tasks',
    title: '任务查看',
    detail: '查看任务',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_scroll_11.jpg',
    glyphAssetId: 'builds-evidence-medallion.tasks',
    fallbackGlyphAssetId: 'utility-glyph-family.records',
    disabled: false,
  },
  {
    id: 'talents',
    title: '天赋模拟',
    detail: '设计天赋',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/spell_nature_natureblessing.jpg',
    glyphAssetId: 'builds-evidence-medallion.talents',
    fallbackGlyphAssetId: 'quick-action-talents-glyph.default',
    disabled: true,
  },
  {
    id: 'gear',
    title: '装备模拟',
    detail: '搭配装备',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_misc_gear_01.jpg',
    glyphAssetId: 'builds-evidence-medallion.gear',
    fallbackGlyphAssetId: 'quick-action-gear-glyph.default',
    disabled: false,
  },
  {
    id: 'simc',
    title: 'SimC 模拟',
    detail: '发起模拟',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_misc_book_09.jpg',
    glyphAssetId: 'builds-evidence-medallion.simc',
    fallbackGlyphAssetId: 'quick-action-simc-glyph.default',
    disabled: false,
  },
]

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

  it('keeps each whole card clickable while pinning command content to opposite edges', () => {
    const source = read('BuildCommandDeck.tsx')
    const styles = read('BuildsHomeCommandDeck.module.scss')
    const ownerStyles = read('owners.module.scss')

    expect(source).toContain('onClick={() => activateBuildCommand(entry, onSelect)}')
    expect(source).toContain('data-role={\'build-command-\' + item.id + \'-glyph\'}')
    expect(ownerStyles).toMatch(/\.nativeControl \{[\s\S]*?display:\s*inline-flex;[\s\S]*?width:\s*auto;/u)
    expect(styles).toMatch(/button\.commandCard \{[\s\S]*?display:\s*grid;[\s\S]*?width:\s*100%;[\s\S]*?grid-template-columns:\s*52px minmax\(0, 1fr\) 18px;/u)
    expect(styles).toMatch(/button\.commandCard \{[\s\S]*?padding:\s*8px 14px 8px 13px;[\s\S]*?text-align:\s*left;/u)
    expect(styles).toMatch(/\.commandCardChevron \{[\s\S]*?justify-self:\s*end;/u)
  })

  it('exports both shared components and their contracts', () => {
    const source = readFileSync(resolve(process.cwd(), 'packages/design-system/src/index.ts'), 'utf8')

    expect(source).toContain("export { BuildClassSelector } from './components/BuildClassSelector'")
    expect(source).toContain("export type { BuildClassSelectorOption, BuildClassSelectorProps } from './components/BuildClassSelector'")
    expect(source).toContain("export { BuildCommandDeck } from './components/BuildCommandDeck'")
    expect(source).toContain("export type { BuildCommandDeckItem } from './components/BuildCommandDeck'")
  })

  it('resolves exactly one selected class with value taking precedence', () => {
    const resolved = resolveBuildClassSelection(classOptions, 'warrior')

    expect(resolved.selectedId).toBe('warrior')
    expect(resolved.selectedOption?.label).toBe('战士')
    expect(resolved.options.filter((option) => option.selected)).toEqual([
      expect.objectContaining({ id: 'warrior' }),
    ])
  })

  it('selects an available class before closing and ignores disabled paths', () => {
    const events: string[] = []

    expect(activateBuildClassOption(classOptions[0]!, false, (id) => events.push(`select:${id}`), () => events.push('close'))).toBe(true)
    expect(events).toEqual(['select:mage', 'close'])

    expect(activateBuildClassOption(classOptions[2]!, false, (id) => events.push(`select:${id}`), () => events.push('close'))).toBe(false)
    expect(activateBuildClassOption(classOptions[1]!, true, (id) => events.push(`select:${id}`), () => events.push('close'))).toBe(false)
    expect(events).toEqual(['select:mage', 'close'])
  })

  it('preserves incoming deck order and blocks item-disabled or loading activation', () => {
    const readyEntries = buildCommandDeckEntries(commandItems)
    expect(readyEntries.map((entry) => entry.item.id)).toEqual(['tasks', 'talents', 'gear', 'simc'])

    const selected: string[] = []
    expect(activateBuildCommand(readyEntries[0]!, (id) => selected.push(id))).toBe(true)
    expect(activateBuildCommand(readyEntries[1]!, (id) => selected.push(id))).toBe(false)
    expect(activateBuildCommand(buildCommandDeckEntries(commandItems, true)[0]!, (id) => selected.push(id))).toBe(false)
    expect(selected).toEqual(['tasks'])
  })

  it('publishes the registered fallback slot for each command glyph', () => {
    const entries = buildCommandDeckEntries(commandItems)

    expect(entries.map((entry) => entry.fallbackGlyphSlotId)).toEqual([
      'asset_slot.utility-glyph-family',
      'asset_slot.quick-action-talents-glyph',
      'asset_slot.quick-action-gear-glyph',
      'asset_slot.quick-action-simc-glyph',
    ])
  })

  it('keeps the selector overlay stack above the shared ProductTabBar owner', () => {
    const selectorStyles = read('BuildsHomeCommandDeck.module.scss')
    const tabBarStyles = read('TabBar.module.scss')

    expect(tabBarStyles).toMatch(/\.root\s*\{[\s\S]*?z-index:\s*100;/u)
    expect(selectorStyles).toMatch(/\.classSelectorScrim\s*\{[\s\S]*?z-index:\s*calc\(var\(--z-toast\) \+ 1\);/u)
    expect(selectorStyles).toMatch(/\.classSelectorSheet\s*\{[\s\S]*?z-index:\s*calc\(var\(--z-toast\) \+ 2\);/u)
  })
})
