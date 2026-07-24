import { describe, expect, it, vi } from 'vitest'

vi.mock('@tarojs/components', () => ({
  Button: 'button',
  ScrollView: 'scroll-view',
  Text: 'text',
  View: 'view',
}))

import type { GearEnhancementSelection } from '@wow-mini/domain'

import {
  candidateVariantEmptyCopy,
  resolveEnhancementSocketRows,
} from './GearEditorSheets'

const emptySelection: GearEnhancementSelection = {
  gemOptionIds: [],
  enchantOptionId: '',
  embellishmentOptionId: '',
  craftedOptionId: '',
  catalystOptionId: '',
}

describe('gear editor sheet behavior', () => {
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
