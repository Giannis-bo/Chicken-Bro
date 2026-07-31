import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/components', () => ({
  Button: 'button',
  Image: 'image',
  ScrollView: 'scroll-view',
  Text: 'text',
  View: 'view',
}))

import type { GearEnhancementSelection } from '@wow-mini/domain'

import {
  candidateVariantEmptyCopy,
  GearCandidateEditorSheet,
  GearEnhancementEditorSheet,
  resolveEnhancementSocketRows,
} from './GearEditorSheets'

const emptySelection: GearEnhancementSelection = {
  gemOptionIds: [],
  enchantOptionId: '',
  embellishmentOptionId: '',
  craftedOptionId: '',
  catalystOptionId: '',
}

const editorStyles = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearEditorSheets.module.scss',
), 'utf8')

describe('gear editor sheet behavior', () => {
  it('keeps candidate facts, notices, and enhancement choices above the readable type floor', () => {
    expect(editorStyles).toMatch(/\.candidateCopy > view text:first-child \{[^}]*font-size:\s*11px;/u)
    expect(editorStyles).toMatch(/\.candidateCopy > view text:last-child,[\s\S]*?\.candidateCopy > text \{[^}]*font-size:\s*9px;/u)
    expect(editorStyles).toMatch(/\.detailHeading text:first-child \{[^}]*font-size:\s*11px;/u)
    expect(editorStyles).toMatch(/\.detailHeading text:last-child,[\s\S]*?\.detailSummary \{[^}]*font-size:\s*9px;/u)
    expect(editorStyles).toMatch(/\.notice,[\s\S]*?\.blockerGroup \{[^}]*font-size:\s*9px;/u)
    expect(editorStyles).toMatch(/\.optionControl \{[^}]*min-height:\s*40px;[^}]*font-size:\s*9px;/u)
    expect(editorStyles).toMatch(/\.workbenchSheet \{[^}]*grid-template-rows:\s*50px minmax\(0, 1fr\) 52px;/u)
  })

  it('lays candidate cards in two-card rows', () => {
    expect(editorStyles).toMatch(/\.candidatePair \{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);/u)
  })

  it('renders the candidate item icon when the candidate provides a trusted media URL', () => {
    const markup = renderToStaticMarkup(createElement(GearCandidateEditorSheet, {
      slotLabel: '头部',
      candidates: [{
        id: 'head-heroic',
        itemId: '123',
        label: '吞噬者守护的头盔',
        levelLabel: '装等 298',
        sourceLabel: '团队副本',
        statSummary: '暴击 197 · 急速 112',
        badgeLabels: [],
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helmet_151.jpg',
        state: 'ready' as const,
      }],
      selectedCandidateId: 'head-heroic',
      draft: null,
      canApply: false,
      onSelectCandidate: () => undefined,
      onSelectVariant: () => undefined,
      onSelectCraftedStat: () => undefined,
      onApply: () => undefined,
      onClose: () => undefined,
    }))

    expect(markup).toContain('data-role="gear-candidate-media"')
    expect(markup).toContain('src="https://render.worldofwarcraft.com/us/icons/56/inv_helmet_151.jpg"')
  })

  it('places selected candidate details below its two-card row', () => {
    const markup = renderToStaticMarkup(createElement(GearCandidateEditorSheet, {
      slotLabel: '头部',
      candidates: [
        {
          id: 'head-heroic',
          itemId: '123',
          label: '吞噬者守护的头盔',
          levelLabel: '装等 298',
          sourceLabel: '团队副本',
          statSummary: '暴击 197 · 急速 112',
          badgeLabels: ['英雄'],
          state: 'ready' as const,
        },
        {
          id: 'head-mythic',
          itemId: '123',
          label: '吞噬者守护的头盔',
          levelLabel: '装等 285',
          sourceLabel: '团队副本',
          statSummary: '暴击 176 · 急速 103',
          badgeLabels: ['史诗'],
          state: 'ready' as const,
        },
        {
          id: 'head-raidfinder',
          itemId: '123',
          label: '吞噬者守护的头盔',
          levelLabel: '装等 272',
          sourceLabel: '团队副本',
          statSummary: '暴击 131 · 急速 79',
          badgeLabels: ['随机团队'],
          state: 'ready' as const,
        },
      ],
      selectedCandidateId: 'head-heroic',
      draft: {
        slot: 'head',
        candidate: { itemId: '123', variantKey: 'heroic', blockers: [] },
        requiresVariantSelection: true,
        selectedVariantKey: 'heroic',
        requiresCraftedStatSelection: false,
        selectedCraftedOptionId: '',
        variants: [{
          key: 'heroic',
          label: '英雄',
          difficultyLabel: '英雄',
          ilevel: 298,
          state: 'ready' as const,
          blockers: [],
        }],
        craftedStatOptions: [],
      },
      canApply: true,
      onSelectCandidate: () => undefined,
      onSelectVariant: () => undefined,
      onSelectCraftedStat: () => undefined,
      onApply: () => undefined,
      onClose: () => undefined,
    }))

    const detailIndex = markup.indexOf('data-role="gear-candidate-detail"')
    expect(markup).toContain('data-candidate-draft-item-id="123"')
    expect(detailIndex).toBeGreaterThan(markup.indexOf('data-candidate-id="head-mythic"'))
    expect(detailIndex).toBeLessThan(markup.indexOf('data-candidate-id="head-raidfinder"'))
  })

  it('renders crafted stats as selectable resolver options instead of display-only facts', () => {
    const markup = renderToStaticMarkup(createElement(GearCandidateEditorSheet, {
      slotLabel: '头部',
      candidates: [{
        id: 'crafted-head',
        itemId: '244743',
        label: '以太流明遮目镜',
        levelLabel: '装等 285',
        sourceLabel: '制造装备',
        statSummary: '智力 200',
        badgeLabels: ['布甲'],
        state: 'ready' as const,
      }],
      selectedCandidateId: 'crafted-head',
      draft: {
        slot: 'head',
        candidate: { itemId: '244743' },
        requiresVariantSelection: true,
        selectedVariantKey: 'crafted-myth-285',
        requiresCraftedStatSelection: true,
        selectedCraftedOptionId: 'crafted-stats-haste',
        variants: [{
          key: 'crafted-myth-285',
          label: '制造装备',
          difficultyLabel: '制造装备',
          ilevel: 285,
          state: 'ready' as const,
          blockers: [],
        }],
        craftedStatOptions: [{
          key: 'haste',
          optionId: 'crafted-stats-haste',
          label: '急速',
          simcOptions: ['crafted_stats=36'],
          state: 'ready' as const,
          blockers: [],
        }],
      },
      canApply: true,
      onSelectCandidate: () => undefined,
      onSelectVariant: () => undefined,
      onSelectCraftedStat: () => undefined,
      onApply: () => undefined,
      onClose: () => undefined,
    }))

    expect(markup).toContain('制造属性')
    expect(markup).toContain('data-role="gear-crafted-stat-option"')
    expect(markup).toContain('data-crafted-option-id="crafted-stats-haste"')
    expect(markup).toContain('data-active="true"')
    expect(markup).toContain('data-candidate-draft-crafted-option-id="crafted-stats-haste"')
    expect(markup).not.toContain('仅展示')
  })

  it('shows the equipment identity before configuring its enhancements', () => {
    const markup = renderToStaticMarkup(createElement(GearEnhancementEditorSheet, {
      slotLabel: '头部',
      item: {
        label: '吞噬者守护的头盔',
        levelLabel: '装等 298',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helmet_151.jpg',
      },
      draft: emptySelection,
      socketCount: 0,
      options: [],
      onSetGem: () => undefined,
      onSetSingle: () => undefined,
      onConfirm: () => undefined,
      onClose: () => undefined,
    }))

    expect(markup).toContain('data-role="gear-enhancement-item-media"')
    expect(markup).toContain('src="https://render.worldofwarcraft.com/us/icons/56/inv_helmet_151.jpg"')
    expect(markup.indexOf('data-role="gear-enhancement-item"')).toBeLessThan(markup.indexOf('data-role="gear-enhancement-no-sockets"'))
  })

  it('focuses the requested enhancement kind while letting the player switch between compatible equipment', () => {
    const markup = renderToStaticMarkup(createElement(GearEnhancementEditorSheet, {
      requestedKind: 'socket',
      activeSlot: 'head',
      compatibleSlots: [
        {
          slot: 'head',
          label: '头部',
          item: { label: '吞噬者守护的头盔', levelLabel: '装等 298' },
          summary: '1 个宝石插槽',
          selected: true,
        },
        {
          slot: 'finger1',
          label: '戒指 1',
          item: { label: '虚空纹章戒指', levelLabel: '装等 298' },
          summary: '1 个宝石插槽',
          selected: false,
        },
      ],
      slotLabel: '头部',
      item: { label: '吞噬者守护的头盔', levelLabel: '装等 298' },
      draft: emptySelection,
      socketCount: 1,
      options: [{ id: 'gem-haste', kind: 'socket', label: '迅捷宝石', selected: false }],
      onSelectSlot: () => undefined,
      onSetGem: () => undefined,
      onSetSingle: () => undefined,
      onConfirm: () => undefined,
      onClose: () => undefined,
    }))

    expect([...markup.matchAll(/data-role="gear-enhancement-compatible-slot"/gu)]).toHaveLength(2)
    expect(markup).toContain('data-active-slot="head"')
    expect(markup).toContain('data-has-item="true"')
    expect(markup).toContain('data-option-count="1"')
    expect(markup).toContain('data-requested-kind="socket"')
    expect(markup).toContain('data-socket-count="1"')
    expect(markup).toContain('data-enhancement-kind="socket"')
    expect(markup).not.toContain('data-enhancement-kind="enchant"')
    expect(markup).not.toContain('data-enhancement-kind="embellishment"')
  })

  it('renders an icon-bearing option for gem, enchant, and embellishment choices', () => {
    const markup = renderToStaticMarkup(createElement(GearEnhancementEditorSheet, {
      slotLabel: '头部',
      draft: {
        ...emptySelection,
        gemOptionIds: ['gem-haste'],
        enchantOptionId: 'enchant-haste',
        embellishmentOptionId: 'embellishment-armor',
      },
      socketCount: 1,
      options: [
        {
          id: 'gem-haste',
          kind: 'socket' as const,
          label: '迅捷宝石',
          iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_10_jewelcrafting_gem1.jpg',
          selected: true,
        },
        {
          id: 'enchant-haste',
          kind: 'enchant' as const,
          label: '迅捷附魔',
          iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_enchanting_wod_crystal.jpg',
          selected: true,
        },
        {
          id: 'embellishment-armor',
          kind: 'embellishment' as const,
          label: '强化护甲片',
          iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_10_enchanting2_elementalshard_color1.jpg',
          selected: true,
        },
      ],
      onSetGem: () => undefined,
      onSetSingle: () => undefined,
      onConfirm: () => undefined,
      onClose: () => undefined,
    }))

    expect([...markup.matchAll(/data-role="gear-enhancement-option-media"/gu)]).toHaveLength(3)
    expect(markup).toContain('src="https://render.worldofwarcraft.com/us/icons/56/inv_10_jewelcrafting_gem1.jpg"')
    expect(markup).toContain('src="https://render.worldofwarcraft.com/us/icons/56/inv_enchanting_wod_crystal.jpg"')
    expect(markup).toContain('src="https://render.worldofwarcraft.com/us/icons/56/inv_10_enchanting2_elementalshard_color1.jpg"')
  })

  it('keeps socket capacity separate from the packed gem sequence', () => {
    expect(resolveEnhancementSocketRows(emptySelection, 3)).toEqual([
      { socketIndex: 0, selectedId: '', selectable: true },
      { socketIndex: 1, selectedId: '', selectable: false },
      { socketIndex: 2, selectedId: '', selectable: false },
    ])
    expect(resolveEnhancementSocketRows({ ...emptySelection, gemOptionIds: ['gem-a'] }, 3)).toEqual([
      { socketIndex: 0, selectedId: 'gem-a', selectable: true },
      { socketIndex: 1, selectedId: '', selectable: true },
      { socketIndex: 2, selectedId: '', selectable: false },
    ])
  })

  it('distinguishes a legal base candidate from missing backend variants', () => {
    expect(candidateVariantEmptyCopy({ requiresVariantSelection: false, variants: [] })).toBe('此候选无需选择等级轨道')
    expect(candidateVariantEmptyCopy({ requiresVariantSelection: true, variants: [] })).toBe('后端未返回可校验等级轨道')
  })
})
