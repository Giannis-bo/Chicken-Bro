import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('SimC active Taro canonical contract', () => {
  it('uses backend options and Exact refs for confirm, submit, and owner-scoped read', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simc.tsx',
    ), 'utf8')

    expect(source).toContain('wowApi.simulator.options()')
    expect(source).toContain("storageKey('simc.buildContext')")
    expect(source).toContain('selectionIntent: canonicalContext.selectionIntent')
    expect(source).toContain('sourceRef: canonicalContext.sourceRef')
    expect(source).toContain('profileRef: canonicalContext.profileRef')
    expect(source).toContain('executionIntent: canonicalContext.executionIntent')
    expect(source).toContain('wowApi.simulator.exactSimcConfirm')
    expect(source).toContain('wowApi.simulator.exactSimcSubmit')
    expect(source).toContain('wowApi.simulator.exactSimcRead')
    expect(source).not.toContain('wowApi.websim.gearStatSnapshot')
    expect(source).not.toContain('profileContext')
    expect(source).not.toContain('wowApi.simulator.analyze')
    expect(source).not.toContain('wowApi.websim.gearStats')
    expect(source).not.toContain("analysisType: 'simcraft'")
    expect(source).not.toContain('analysisType:')
    expect(source).not.toContain('templateContext:')
    expect(source).not.toMatch(/const races\s*=/)
    expect(source).not.toMatch(/const durations\s*=/)
    expect(source).not.toContain('scenarioOptions')
  })

  it('fences confirm or submit against stale input without a legacy profile or stat-snapshot loop', () => {
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
    expect(source.match(/submissionSession\.current\.isCurrent\(token\)/g)?.length ?? 0).toBeGreaterThanOrEqual(7)
    expect(source).not.toContain('pendingSignature')
    expect(source).not.toContain('属性快照签名在轮询期间发生变化')
    expect(source.match(/disabled=\{submitting\}/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
    expect(source.match(/if \(submittingRef\.current\) return/g)?.length ?? 0).toBeGreaterThanOrEqual(3)
    expect(components).toContain('disabled?: boolean | undefined')
  })

  it('wires real gear-template selection and renders scenario-owned duration as read-only', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simc.tsx',
    ), 'utf8')
    const components = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/SimcSubmitComponents.tsx',
    ), 'utf8')

    expect(source).toContain("wowApi.templates.fetch('gear')")
    expect(source).toContain('setGearSourceId(next.id)')
    expect(source).not.toContain('onSelect={() => {}}')
    expect(source).not.toContain('onDurationSelect={() => {}}')
    expect(components).toContain('data-readonly="true"')
    expect(components).not.toContain('onDurationSelect: (index: number) => void')
  })

  it('publishes backend-owned specialization support semantics for the real WeChat matrix', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simc.tsx',
    ), 'utf8')

    expect(source).toContain('data-simc-specialization-id=')
    expect(source).toContain('data-simc-specialization-supported=')
    expect(source).toContain('data-simc-specialization-blocker-code=')
    expect(source).toContain('data-simc-options-state=')
    expect(source).toContain("dataSelectorClass('simc-specialization-id'")
    expect(source).toContain("dataSelectorClass('simc-specialization-supported'")
    expect(source).toContain("dataSelectorClass('simc-specialization-blocker-code'")
    expect(source).toContain("dataSelectorClass('simc-options-state'")
  })
})
