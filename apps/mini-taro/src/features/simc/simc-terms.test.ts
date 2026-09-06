import { describe, expect, it } from 'vitest'
import { simcLabel, simcResourceName, simcSpellName } from './simc-terms'
import elementalReport from '../../../../../tests/fixtures/simc/giannis_elemental_report.json'

describe('mainland Chinese SimC terminology', () => {
  it('names every ability and buff in the real Giannis elemental report', () => {
    const unresolved = [
      ...elementalReport.abilities.map((entry, index) => ({ raw: entry.name, label: simcSpellName(entry.name, '技能', index) })),
      ...elementalReport.buffs.map((entry, index) => ({ raw: entry.name, label: simcSpellName(entry.name, '增益', index) })),
    ].filter(({ label }) => label.includes('待收录') || /[A-Za-z]/u.test(label))
    expect(unresolved).toEqual([])
  })
  it('distinguishes player, ancestor, elemental pets and different stat effects', () => {
    expect(simcSpellName('lava_burst', '技能', 0)).toBe('熔岩爆裂')
    expect(simcSpellName('ancestor: lava_burst', '技能', 0)).toBe('先祖：熔岩爆裂')
    expect(simcSpellName('primal_fire_elemental: fire_blast', '技能', 0)).toBe('原始火元素：火焰冲击')
    expect(simcSpellName('primal_storm_elemental: wind_gust', '技能', 0)).toBe('原始风暴元素：呼啸狂风')
    expect(simcSpellName('elemental_blast_critical_strike', '增益', 0)).toBe('元素冲击：爆击')
    expect(simcSpellName('debilitating_venom_Crit', '增益', 0)).toBe('衰弱毒液（爆击）')
    expect(simcSpellName('empowering_venom_Vers', '增益', 0)).toBe('强化毒液（全能）')
  })
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
