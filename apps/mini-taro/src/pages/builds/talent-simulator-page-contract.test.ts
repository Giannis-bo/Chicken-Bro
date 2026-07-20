import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('talent simulator authoritative edit contract', () => {
  it('does not render or request the obsolete WebSim status and community blocks', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).not.toContain('TalentImportStatus')
    expect(source).not.toContain('TalentCommunityRow')
    expect(source).not.toContain('wowApi.websim.talentImport')
    expect(source).not.toContain('data-region="import_panel"')
    expect(source).not.toContain('data-region="community_builds"')
  })

  it('keeps the action bar at the bottom and gives the vacated space to the talent tree', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')
    const style = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.module.scss',
    ), 'utf8')
    const geometryContract = JSON.parse(readFileSync(resolve(
      process.cwd(),
      'docs/design/current-ui/route-geometry-contract.json',
    ), 'utf8')) as { routes: Array<{ route: string, requiredRegionIds: string[] }> }
    const componentContract = JSON.parse(readFileSync(resolve(
      process.cwd(),
      'docs/design/current-ui/routes/talent-simulator/component-contract.json',
    ), 'utf8')) as {
      stateContract: { stableRegionCount: number }
      layoutContract: {
        regionBoundsCssPx: {
          tree_canvas: { height: number }
          legend_bar: { y: number }
          bottom_action_bar: { y: number }
        }
      }
      productOverrides?: Array<{ excludedTargetRegions: string[], layoutRule: string }>
    }

    expect(source).toContain('targetRegionCount={8}')
    expect(style).toContain('height: 700px')
    expect(style).toMatch(/\.graphRegion \{[\s\S]*?height: 461px/u)
    expect(style).toMatch(/\.legendRegion \{[\s\S]*?top: 612px/u)
    expect(style).toMatch(/\.actionsRegion \{[\s\S]*?top: 650px/u)
    expect(style).not.toContain('importRegion')
    expect(style).not.toContain('communityRegion')
    expect(geometryContract.routes.find((route) => route.route === 'talent_simulator')?.requiredRegionIds).toEqual([
      'specialization_selector',
      'talent_tabs',
      'points_summary',
      'talent_graph',
      'talent_legend',
      'talent_actions',
    ])
    expect(componentContract.stateContract.stableRegionCount).toBe(8)
    expect(componentContract.productOverrides?.[0]?.excludedTargetRegions).toEqual([
      'websim_panel',
      'community_template_row',
    ])
    expect(componentContract.productOverrides?.[0]?.layoutRule).toBe(
      'tree_canvas consumes the excluded regions vertical space while bottom_action_bar keeps its original bottom position',
    )
    expect(componentContract.layoutContract.regionBoundsCssPx.tree_canvas.height).toBe(461.09)
    expect(componentContract.layoutContract.regionBoundsCssPx.legend_bar.y).toBe(669.18)
    expect(componentContract.layoutContract.regionBoundsCssPx.bottom_action_bar.y).toBe(706.28)
  })

  it('locks the route surface while leaving vertical scrolling to the talent graph viewport', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')
    const appShellSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/AppShell.tsx',
    ), 'utf8')
    const ownerStyleSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/owners.module.scss',
    ), 'utf8')

    expect(source).toContain('bodyScrollable={false}')
    expect(appShellSource).toContain('bodyScrollable?: boolean')
    expect(appShellSource).toContain("!bodyScrollable && ownerStyle('shellBodyLocked')")
    expect(ownerStyleSource).toMatch(/\.shellBodyLocked \{[\s\S]*?overflow-y: hidden;/u)
  })

  it('uses bootstrap hero trees for an interactive hero selector and reloads the selected tree', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).toContain("const [selectedHeroKey, setSelectedHeroKey] = useState(safeDecode(router.params['hero']) || '')")
    expect(source).toContain('heroKey: selectedHeroKey || selection.heroKey')
    expect(source).toContain('heroTalentOptions(data?.bootstrap, data?.selection)')
    expect(source).toContain("if (item.id === 'hero')")
    expect(source).toContain('setSelectedHeroKey(option.id)')
    expect(source).not.toContain("? [{ id: data?.talents.heroKey || 'hero', label: heroSection.title }]")
  })

  it('uses the verified source-lattice layout for every class, specialization and hero tree', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).not.toContain('sourceLatticeSample')
    expect(source).toContain("layoutMode: 'source_lattice'")
  })

  it('lets every source-lattice tree keep its roomier row spacing through vertical reach', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).toContain('allowVerticalOverflow')
  })

  it('renders the active hero root talent icon in the hero selector crest', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    ), 'utf8')

    expect(source).toContain("heroTalentIcon(data?.talents.nodes ?? [])")
    expect(source).toContain("...(heroIconUrl ? { iconUrl: heroIconUrl } : {})")
  })

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
    expect(source).toContain('runFencedTalentSave')
    expect(source).toContain('isCurrent: () => validationSequence.current === operationSequence')
    expect(source).toContain('if (!decision.accepted || !code)')
    expect(source).toContain('setNodeAvailability(route.data.talents.nodeAvailability)')
    expect(source).toContain('availability: nodeAvailability')
    expect(source).toContain('setNodeAvailability(result.payload.nodeAvailability)')
    expect(source).toContain('setNodeAvailability(result.payload.validation.nodeAvailability)')
  })
})
