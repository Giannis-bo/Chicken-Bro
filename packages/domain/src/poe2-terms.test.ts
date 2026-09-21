import {expect, it} from 'vitest'
import {poe2Term, poe2GemInput, poe2Slots, poe2Config, poe2Unsupported} from './poe2-terms'

it('uses source-verified national names and exact Roman tiers without guessing unknowns', () => {
  expect(poe2Term('Gemling Legionnaire', 'ascendancy')).toBe('古灵使徒斗士')
  expect(poe2Term('Shield Wall', 'gem')).toBe('盾墙')
  expect(poe2Term('Unknown III', 'gem')).toBe('Unknown III（国服名称待核实）')
  expect(poe2GemInput('盾墙')).toBe('Shield Wall')
  expect(poe2GemInput('Unknown III')).toBe('Unknown III')
  expect(() => poe2GemInput('未知技能 III')).toThrow('国服名称待核实')
})
it('localizes field labels without changing their engine keys', () => {
  expect(poe2Slots['Ring 1']).toBe('戒指 1')
  expect(poe2Config({enemyIsBoss: 'Pinnacle', conditionFullLife: true, internalField: 1})).toEqual(['敌人类型：巅峰首领', '满生命：是'])
  expect(poe2Unsupported('Unrecognized gem: Shield Wall')).toBe('引擎未识别技能：盾墙')
  expect(poe2Unsupported('Your unreserved Spirit is negative')).toContain('可用精魂为负')
  expect(poe2Unsupported('You have too many gem groups allocated. Max allowed is 9. You have 11 non-item/non-granted gem groups allocated.')).toContain('最多 9 组，当前启用了 11 组')
  expect(poe2Unsupported('Charm 2: Recover 200 Life when Used')).toBe('护符 2：使用时回复 200 点生命（引擎未完整支持）')
  expect(poe2Unsupported('Unrecognized gem: ')).toContain('空技能项')
})
