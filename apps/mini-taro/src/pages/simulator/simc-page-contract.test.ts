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

  it('keeps local talent fallback usable and fences confirm or submit against stale input', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simc.tsx',
    ), 'utf8')
    const components = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/SimcSubmitComponents.tsx',
    ), 'utf8')

    expect(source).toContain('simcRouteFromFallback({')
    expect(source).toContain('talentsFromFallback: talentsResult.fromFallback')
    expect(source).not.toContain('homeResult.error, optionsResult.error, talentsResult.error')
    expect(source).toContain('submissionSession.current.unmount()')
    expect(source.match(/submissionSession\.current\.isCurrent\(token\)/g)?.length ?? 0).toBeGreaterThanOrEqual(8)
    expect(source).toContain('pendingSignature')
    expect(source).toContain('属性快照签名在轮询期间发生变化')
    expect(source.match(/disabled=\{submitting\}/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
    expect(source.match(/if \(submittingRef\.current\) return/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
    expect(components).toContain('disabled?: boolean | undefined')
  })
})
