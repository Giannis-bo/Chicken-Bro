import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('talent simulator authoritative edit contract', () => {
  it('validates proposals and exports the current validated state before saving', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).toContain('wowApi.websim.talentValidate')
    expect(source).toContain('wowApi.websim.talentExport')
    expect(source).not.toContain('cycleTalentRank')
    expect(source).not.toContain('selectTalentChoice')
    expect(source).toContain('rawString: exportDecision.code')
    expect(source).not.toContain('rawString: data.talentImport.importCode')
    expect(source).toContain("'已保存到本地，远端未确认'")
    expect(source).toContain("'模板已保存并由远端确认'")
    expect(source).not.toContain('setEditMessage(template ? title')
    expect(source).toContain("connectivityStatus !== 'ready' || validating || saving")
  })
})
