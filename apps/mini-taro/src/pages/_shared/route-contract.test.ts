import fs from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { routeContracts, routePolicy } from '@wow-mini/domain'

describe('Taro source route contract', () => {
  it('registers exactly the 14 current product routes', () => {
    const appConfig = fs.readFileSync(path.join(process.cwd(), 'apps/mini-taro/src/app.config.ts'), 'utf8')
    expect(routeContracts).toHaveLength(routePolicy.registeredRouteCount)
    for (const route of routeContracts) expect(appConfig).toContain(`'${route.targetPage}'`)
  })

  it('has a TSX implementation for every route', () => {
    for (const route of routeContracts) {
      const file = path.join(process.cwd(), 'apps/mini-taro/src', `${route.targetPage}.tsx`)
      expect(fs.existsSync(file), route.routeKey).toBe(true)
      const source = fs.readFileSync(file, 'utf8')
      expect(source).toContain('export default function')
      expect(source).not.toContain('RoutePending')
      expect(source).not.toContain('.wxml')
      expect(source).not.toContain('.wxss')
    }
  })

  it('keeps the active target registry aligned with the 14 product routes', () => {
    const registry = JSON.parse(fs.readFileSync(
      path.join(process.cwd(), 'docs/design/current-ui/target-registry.json'),
      'utf8',
    )) as {
      status: string
      authority: string
      targetRoot: string
      canonicalTargets: readonly {
        route: string
        path: string
        width: number
        height: number
        sha256: string
      }[]
    }
    expect(registry.status).toBe('active')
    expect(registry.authority).toBe('docs/plans/2026-07-14-target-first-14-route-rebuild.md')
    expect(registry.targetRoot).toBe('artifacts/ui-visual-targets/current')
    expect(registry.canonicalTargets).toHaveLength(routePolicy.registeredRouteCount)
    expect(new Set(registry.canonicalTargets.map((target) => target.route)).size).toBe(routePolicy.registeredRouteCount)
    for (const target of registry.canonicalTargets) {
      expect(fs.existsSync(path.join(process.cwd(), target.path)), target.route).toBe(true)
      expect(target.width).toBeGreaterThan(0)
      expect(target.height).toBeGreaterThan(0)
      expect(target.sha256).toMatch(/^[a-f0-9]{64}$/)
    }
  })

  it('keeps the workbench on its target-owned composition', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/builds/workbench.tsx'),
      'utf8',
    )
    expect(source).toContain('WorkbenchSpecSummary')
    expect(source).toContain('WorkbenchReadinessPanel')
    expect(source).toContain('WorkbenchModuleDeck')
    expect(source).toContain('variant="workbench"')
    expect(source).not.toContain('WorkbenchCockpit')
    expect(source).not.toContain('<WowPanel')
    expect(source).not.toContain('<RouteStatePanel')
  })

  it('keeps news_list on its six target-owned regions', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/news/list.tsx'),
      'utf8',
    )
    expect(source).toContain('NewsListSummary')
    expect(source).toContain('NewsListCategoryFilter')
    expect(source).toContain('NewsListFeed')
    expect(source).toContain('NewsListTerminalPanel')
    expect(source).toContain('TrustDisclaimer')
    expect(source).toContain('variant="news-list"')
    expect(source).not.toContain('RankedFeed')
    expect(source).not.toContain('ChannelDock')
    expect(source).not.toContain('<WowPanel')
    expect(source).not.toContain('<RouteStatePanel')
  })

  it('keeps task_detail on its ten-region report composition', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/simulator/task-detail.tsx'),
      'utf8',
    )
    expect(source).toContain('TaskDetailSummary')
    expect(source).toContain('TaskRefreshNotice')
    expect(source).toContain('TaskSimcResult')
    expect(source).toContain('TaskRunContext')
    expect(source).toContain('TaskScenarioGrid')
    expect(source).toContain('TaskAttributeSnapshot')
    expect(source).toContain('TaskCombatPreparation')
    expect(source).toContain('TaskExceptionState')
    expect(source).not.toContain('EvidenceLedger')
    expect(source).not.toContain('<WowPanel')
    expect(source).not.toContain('<RouteStatePanel')
    expect(source).not.toContain('ProductTabBar')
  })

  it('keeps profile/templates on its seven-region local-first composition', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/profile/profile.tsx'),
      'utf8',
    )
    expect(source).toContain('ProfileSummaryPanel')
    expect(source).toContain('ProfileTemplateLibrary')
    expect(source).toContain('ProfileRecentSaves')
    expect(source).toContain('ProfileSettingsList')
    expect(source).toContain('useDidShow')
    expect(source).toContain('if (!confirmation.confirm) return')
    expect(source).not.toContain('ProfileIdentity')
    expect(source).not.toContain('<TemplateLibrary')
    expect(source).not.toContain('EvidenceLedger')
    expect(source).not.toContain('<WowPanel')
    expect(source).not.toContain('<RouteStatePanel')
  })

  it('uses redirect fallback for directly opened non-tab routes', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/_shared/route-runtime.tsx'),
      'utf8',
    )
    expect(source).toContain('const TAB_ROUTES = new Set')
    expect(source).toContain('Taro.redirectTo({ url: fallbackTab })')
  })

  it('invalidates SimC confirmation whenever visible request inputs change', () => {
    const source = fs.readFileSync(
      path.join(process.cwd(), 'apps/mini-taro/src/pages/simulator/simc.tsx'),
      'utf8',
    )
    expect(source).toContain('const invalidateConfirmation = () =>')
    expect(source.match(/invalidateConfirmation\(\)/g)?.length ?? 0).toBeGreaterThanOrEqual(5)
  })
})
