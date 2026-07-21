import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const pageSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/detail.tsx',
), 'utf8')

const styleSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/gear-detail.module.scss',
), 'utf8')

const componentSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearDetailComponents.tsx',
), 'utf8')

const componentStyleSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearDetailComponents.module.scss',
), 'utf8')

const modelSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/gear-detail-model.ts',
), 'utf8')

describe('gear detail fixed workbench contract', () => {
  it('keeps the item-level and attribute summary while removing only the readiness progress rail', () => {
    expect(pageSource).toContain('targetRegionCount={8}')
    expect(pageSource).not.toContain('GearStatusDeck')
    expect(pageSource).not.toContain('gearStatusDeck')
    expect(pageSource).not.toContain('data-region="gear_status"')
    expect(pageSource).not.toContain('GearReadinessOverview')
    expect(pageSource).toContain('GearLoadoutSummary')
    expect(pageSource).toContain('data-region="loadout_summary"')
    expect(modelSource).not.toContain('GearStatusView')
    expect(componentSource).toContain('data-role="gear-item-level"')
    expect(componentSource).toContain('属性概览')
    expect(componentSource).not.toContain('装备就绪度')
    expect(componentSource).not.toContain('gear-ready-count')
    expect(componentSource).not.toContain('gear-readiness-progress')
    expect(componentSource).not.toContain('gear-readiness-track')
    expect(componentSource).not.toContain('gear-readiness-socket')
    expect(componentSource).not.toContain('尚未选择装备')
    expect(componentSource).not.toContain('部分证据')
    expect(componentSource).toContain('summaryPrimaryMetrics')
    expect(componentSource).toContain('summaryMetricColumns')
    expect(componentSource).toContain('primaryMetric')
    expect(componentSource).toContain("['haste', 'critical_strike', 'mastery', 'versatility']")
    expect(componentSource).toContain("['leech', 'avoidance', 'speed']")
    expect(componentStyleSource).toMatch(/\.summaryContent \{[\s\S]*?display:\s*flex;[\s\S]*?flex-direction:\s*column;[\s\S]*?height:\s*100%;/u)
    expect(componentStyleSource).toMatch(/\.summaryPrimaryMetrics \{[\s\S]*?display:\s*flex;/u)
    expect(componentStyleSource).toMatch(/\.summaryPrimaryMetrics \.metric \{[\s\S]*?flex:\s*1 1 0;/u)
    expect(componentStyleSource).toMatch(/\.summaryMetricColumns \{[\s\S]*?display:\s*flex;[\s\S]*?flex:\s*1 1 0;/u)
    expect(componentStyleSource).toMatch(/\.summaryMetricColumn \{[\s\S]*?display:\s*flex;[\s\S]*?flex-direction:\s*column;[\s\S]*?flex:\s*1 1 0;/u)
    expect(componentStyleSource).toMatch(/\.summaryMetricColumn \.metric \{[\s\S]*?flex:\s*1 1 0;/u)
    expect(componentStyleSource).toMatch(/\.summaryMetricColumnRight \.metric \{[\s\S]*?flex:\s*0 0 25%;/u)
    expect(componentStyleSource).toMatch(/\.primaryMetric \{[\s\S]*?font-weight:\s*800;/u)
    expect(styleSource).toMatch(/\.loadoutSummaryRegion \{[\s\S]*?top:\s*61px;[\s\S]*?height:\s*163px;/u)
    expect(styleSource).toMatch(/\.enhancementRegion \{[\s\S]*?top:\s*230px;[\s\S]*?height:\s*44px;/u)
    expect(styleSource).toMatch(/\.workbenchRegion \{[\s\S]*?top:\s*281px;[\s\S]*?height:\s*413px;/u)
    expect(styleSource).toMatch(/\.actionsRegion \{[\s\S]*?top:\s*700px;[\s\S]*?height:\s*40px;/u)
    expect(styleSource).not.toContain('.statusRegion')
    expect(styleSource).not.toContain('.readinessRegion')
  })

  it('locks the route surface while keeping candidate browsing inside the expanded workbench', () => {
    expect(pageSource).toContain('bodyScrollable={false}')
    expect(componentSource).toContain('data-role="gear-candidate-scroll"')
    expect(componentSource).toMatch(/<ScrollView[^>]*data-role="gear-candidate-scroll"[^>]*scrollY/u)
    expect(componentSource).not.toContain('GearReadinessOverview')
    expect(componentSource).not.toContain('data-role="gear-primary-action"')
    expect(componentSource).not.toContain('primaryLabel')
    expect(componentSource).not.toContain('onPrimary')
    expect(componentStyleSource).toMatch(/\.slotColumn \{[\s\S]*?bottom:\s*7px;/u)
    expect(componentStyleSource).toMatch(/\.workbenchCenter \{[\s\S]*?bottom:\s*7px;/u)
    expect(componentStyleSource).toMatch(/\.candidatePanel \{[\s\S]*?bottom:\s*7px;/u)
  })
})
