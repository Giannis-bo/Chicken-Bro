import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('SimC active Taro canonical contract', () => {
  it('uses backend options, canonical build context, and canonical stat snapshots for confirm and final submit', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simc.tsx',
    ), 'utf8')

    expect(source).toContain('wowApi.simulator.options()')
    expect(source).toContain("storageKey('simc.buildContext')")
    expect(source).toContain('wowApi.websim.gearStatSnapshot')
    expect(source).toContain('selectionIntent: canonicalContext.selectionIntent')
    expect(source).toContain('profileContext: canonicalContext.profileContext')
    expect(source).toContain('...confirmation.request')
    expect(source).toContain('statSnapshot: snapshot')
    expect(source).not.toContain('wowApi.websim.gearStats')
    expect(source).not.toContain("analysisType: 'simcraft'")
    expect(source).not.toContain('analysisType:')
    expect(source).not.toContain('templateContext:')
    expect(source).not.toMatch(/const races\s*=/)
    expect(source).not.toMatch(/const durations\s*=/)
    expect(source).not.toContain('scenarioOptions')
  })
})
