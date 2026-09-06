import { describe, expect, it } from 'vitest'
import { simcLabel, simcResourceName, simcSpellName } from './simc-terms'

describe('mainland Chinese SimC terminology', () => {
  it('keeps the fury specialization distinct from the demon hunter resource', () => {
    expect(simcLabel('fury')).toBe('狂怒')
    expect(simcResourceName('fury')).toBe('恶魔之怒')
  })
  it('does not expose inherited dictionary keys or untranslated names', () => {
    expect(simcLabel('constructor')).toBe('名称待收录')
    expect(simcSpellName('__proto__', '技能', 0)).toBe('名称待收录的技能（1）')
    expect(simcSpellName('新技能', '技能', 0)).toBe('新技能')
  })
  it('resolves engine aliases and report-only qualifiers to verified names', () => {
    expect(simcSpellName('crash_lightning', '技能', 0)).toBe('毁灭闪电')
    expect(simcSpellName('lightning_wolf: melee', '技能', 0)).toBe('幽灵狼：自动攻击')
    expect(simcSpellName('potion_of_recklessness_Crit', '增益', 0)).toBe('鲁莽药水（爆击）')
    expect(simcSpellName('potion_of_recklessness_penalty_Vers', '增益', 0)).toBe('鲁莽药水（全能降低）')
  })
})
