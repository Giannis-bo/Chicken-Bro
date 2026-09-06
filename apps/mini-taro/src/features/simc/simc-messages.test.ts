import { describe, expect, it } from 'vitest'

import { simcDiagnosticMessage, simcReadinessLabel, simcRequiredFieldLabel } from './simc-messages'

describe('SimC Chinese operational messages', () => {
  it('distinguishes readiness failures from incomplete character data', () => {
    const expected = {
      READY_FOR_SIMC: '可以模拟', INCOMPLETE_FOR_SIMC: '角色资料待完善', INVALID_LINK: '角色链接无效',
      CHARACTER_NOT_FOUND: '未找到角色', ACCESS_RESTRICTED: '角色资料访问受限', SNAPSHOT_UNAVAILABLE: '角色资料暂不可用',
    }
    for (const [code, label] of Object.entries(expected)) expect(simcReadinessLabel(code)).toBe(label)
    expect(simcReadinessLabel('FUTURE_STATE')).toBe('资料状态暂不可用')
  })

  it('names current character and equipment field paths precisely', () => {
    expect(simcRequiredFieldLabel('character.classKey')).toBe('角色职业')
    expect(simcRequiredFieldLabel('character.realm')).toBe('角色服务器')
    expect(simcRequiredFieldLabel('talents.loadout')).toBe('天赋配置')
    expect(simcRequiredFieldLabel('gear.main_hand')).toBe('主手装备')
    expect(simcRequiredFieldLabel('gear.off_hand.itemId')).toBe('副手装备物品编号')
    expect(simcRequiredFieldLabel('gear.finger1.bonusIds')).toBe('戒指一装备附加属性标识')
    expect(simcRequiredFieldLabel('gear.head.gems')).toBe('头部装备宝石')
    expect(simcRequiredFieldLabel('gear.chest.enchant')).toBe('胸部装备附魔')
    expect(simcRequiredFieldLabel('gearState.unequippedSlots.off_hand')).toBe('副手未装备状态')
  })

  it('maps every current gear blocker without losing its slot or missing detail', () => {
    const slots = ['HEAD', 'NECK', 'SHOULDER', 'BACK', 'CHEST', 'WRIST', 'HANDS', 'WAIST', 'LEGS', 'FEET', 'FINGER1', 'FINGER2', 'TRINKET1', 'TRINKET2', 'MAIN_HAND', 'OFF_HAND']
    for (const slot of slots) {
      for (const semantic of ['', '_ITEMLEVEL', '_BONUSIDS', '_GEMS', '_ENCHANT']) {
        const message = simcDiagnosticMessage(`GEAR_${slot}${semantic}_MISSING`)
        expect(message).toMatch(/^缺少/u)
        expect(message).not.toMatch(/[A-Za-z]/u)
        expect(message).not.toContain('暂不可用')
      }
    }
    expect(simcDiagnosticMessage('GEAR_MAIN_HAND_ENCHANT_MISSING')).toBe('缺少主手装备附魔')
    expect(simcDiagnosticMessage('INVALID_GEAR_OFF_HAND_ITEMLEVEL')).toBe('副手装备物品等级无效')
  })

  it('distinguishes missing identity, source, compiler and runtime causes', () => {
    expect(simcDiagnosticMessage('CHARACTER_SPEC_MISSING')).toBe('缺少角色专精')
    expect(simcDiagnosticMessage('SOURCE_PROVENANCE_MISSING')).toBe('缺少角色资料来源记录，请重新读取角色')
    expect(simcDiagnosticMessage('COMPILER_UNAVAILABLE')).toBe('角色配置编译服务暂不可用，请稍后重试')
    expect(simcDiagnosticMessage('RUNTIME_UNAVAILABLE')).toBe('云端模拟引擎暂不可用或暂不支持该专精')
    expect(simcDiagnosticMessage('SIMC_TIMEOUT')).toBe('云端模拟超时，请稍后重试')
  })

  it('covers execution attempt states and does not invent a successful result', () => {
    expect(simcDiagnosticMessage('RUNNING')).toBe('正在执行')
    expect(simcDiagnosticMessage('QUEUED')).toBe('等待执行')
    expect(simcDiagnosticMessage('SIMC_RESULT_VALID')).toBe('模拟结果已验证')
    expect(simcDiagnosticMessage('SIMC_EXECUTION_FAILED')).toBe('云端模拟执行失败，请检查角色资料和战斗设置')
  })

  it('preserves Chinese detail and safely handles unknown English messages and prototype names', () => {
    expect(simcDiagnosticMessage('FUTURE_ERROR', '  此角色资料尚未公开，请联系角色本人  ')).toBe('此角色资料尚未公开，请联系角色本人')
    for (const code of ['FUTURE_ERROR', '__proto__', 'constructor', 'toString', '']) {
      expect(simcDiagnosticMessage(code, 'Runtime failed for account X')).toBe('暂时无法完成此操作，请稍后重试')
      expect(simcRequiredFieldLabel(code)).toBe('未识别的资料项')
    }
    expect(simcDiagnosticMessage('SIMC_TIMEOUT', 'Engine timeout')).toContain('超时')
    expect(simcRequiredFieldLabel('角色来源')).toBe('角色来源')
    expect(simcDiagnosticMessage('FUTURE_ERROR', '角色 Engine 不可用')).not.toMatch(/[A-Za-z]/u)
  })
})
