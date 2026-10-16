import { describe, expect, it } from 'vitest'
import { isCharacterCollection } from './simc-characters'

const item = { id: '84b30edc-39ba-4bd6-8ac2-7a34c0a1c912', name: '炸鸡', realm: 'Silver Hand', region: 'cn', sourceUrl: 'https://raider.io/characters/cn/silver-hand/Giannis' }
describe('account character collection', () => {
  it('accepts empty and selected account shortcuts and rejects references outside the collection', () => {
    expect(isCharacterCollection({ items: [], selectedId: null })).toBe(true)
    expect(isCharacterCollection({ items: [item], selectedId: item.id })).toBe(true)
    expect(isCharacterCollection({ items: [], selectedId: item.id })).toBe(false)
    expect(isCharacterCollection({ items: [item, item], selectedId: item.id })).toBe(false)
    expect(isCharacterCollection({ items: [item, item, item, item], selectedId: item.id })).toBe(false)
  })
  it('rejects non-character source hosts and unbounded or extra identity fields', () => {
    for (const patch of [{ sourceUrl: 'https://evil.invalid/path' }, { name: 'x'.repeat(65) }, { region: 'xx' }, { userId: 'owner' }]) {
      expect(isCharacterCollection({ items: [{ ...item, ...patch }], selectedId: item.id })).toBe(false)
    }
  })
})
