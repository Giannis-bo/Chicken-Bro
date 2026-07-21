import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const pageSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/builds.tsx',
), 'utf8')

const styleSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/builds-home.module.scss',
), 'utf8')

function executePageModule(): Record<string, unknown> {
  const transpiled = ts.transpileModule(pageSource, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  const module = { exports: {} as Record<string, unknown> }
  runInNewContext(transpiled, {
    exports: module.exports,
    module,
    require: () => ({}),
  })
  return module.exports
}

describe('builds home page composition contract', () => {
  it('composes only the title, class selector, command deck, and shared shell chrome', () => {
    expect(pageSource).toContain('title="职业专精"')
    expect(pageSource).toContain('<BuildClassSelector')
    expect(pageSource).toContain('<BuildCommandDeck')
    expect(pageSource).toContain('<RouteStage')
    expect(pageSource).toContain('<AppShell bodyScrollable={false} tabRoot>')
    expect(pageSource).not.toContain('Picker')
    expect(pageSource).not.toContain('BuildSpecializationOverview')
    expect(pageSource).not.toContain('BuildEvidenceNavigator')
    expect(pageSource).not.toContain('BuildWorkspaceEntry')
    expect(pageSource).not.toContain('BuildWorkflowTimeline')
    expect(pageSource).not.toContain('openWorkflow')
    expect(pageSource).not.toContain('useWorkspaceAction')
  })

  it('hydrates and persists the class context before updating React state', () => {
    expect(pageSource).toContain('useState(() => readBuildsHomeContext())')
    expect(pageSource).toContain('buildBuildsHomeModel({')
    expect(pageSource).toContain('context,')
    expect(pageSource).toMatch(/const nextContext = selectBuildsHomeClass\(classKey\)[\s\S]*?setContext\(nextContext\)/u)
  })

  it('adapts the model classKey explicitly to the shared selector id contract', () => {
    expect(pageSource).toMatch(/model\.classOptions\.map\(\(\{ classKey, \.\.\.option \}\) => \(\{[\s\S]*?\.\.\.option,[\s\S]*?id: classKey,[\s\S]*?\}\)\)/u)
    expect(pageSource).toContain('options={classOptions}')
    expect(pageSource).toContain('value={model.selectedClassKey ?? \'\'}')
  })

  it('executes the ready composition gate against the current route state', () => {
    const pageModule = executePageModule() as {
      isBuildsHomeReadyComposition?: (input: {
        routeState: string
        hasCurrentData: boolean
        selectedClassKey?: string
        launchSpecId?: string
      }) => boolean
    }
    const isReady = pageModule.isBuildsHomeReadyComposition
    expect(isReady).toBeTypeOf('function')
    const previousValidModel = {
      hasCurrentData: true,
      selectedClassKey: 'mage',
      launchSpecId: '法师-冰霜',
    }

    expect(isReady?.({ routeState: 'ready', ...previousValidModel })).toBe(true)
    expect(isReady?.({ routeState: 'loading', ...previousValidModel })).toBe(false)
    expect(isReady?.({ routeState: 'error', ...previousValidModel })).toBe(false)
    expect(isReady?.({ routeState: 'blocked', ...previousValidModel })).toBe(false)
  })

  it('keeps tasks independent and sends exact launch payloads to the four existing routes', () => {
    expect(pageSource).toContain("id === 'tasks' ? {} : { spec: item.specId }")
    expect(pageSource).toContain("navigateTo('/pages/builds/talent-simulator', specializationParams)")
    expect(pageSource).toContain("navigateTo('/pages/builds/detail', { ...specializationParams, query: 'gear' })")
    expect(pageSource).toContain("navigateTo('/pages/simulator/simc', { ...specializationParams, from: 'builds' })")
    expect(pageSource).toContain("navigateTo('/pages/simulator/tasks', { from: 'builds' })")
    expect(pageSource).toMatch(/if \(!item \|\| item\.disabled \|\| \(id !== 'tasks' && !item\.specId\)\) return/u)
    expect(pageSource).toContain("...(id === 'tasks' ? {} : { specId: item.specId })")
  })

  it('keeps route state outside ready cards and locks business scrolling above the shared tab bar', () => {
    expect(pageSource).toContain('data-region="class_selector"')
    expect(pageSource).toContain('data-region="command_deck"')
    expect(pageSource).toContain('<RouteColumn')
    expect(pageSource).toContain('<RouteStatePanel')
    expect(pageSource).toContain('const ready = isBuildsHomeReadyComposition({')
    expect(pageSource).toMatch(/rightAction=\{ready \? \([\s\S]*?<RouteRegion[\s\S]*?data-region="class_selector"[\s\S]*?<BuildClassSelector/u)
    expect(pageSource).not.toMatch(/<RouteColumn[\s\S]*?data-region="class_selector"/u)
    expect(styleSource).toMatch(/\.surface \{[\s\S]*?min-height:\s*0;[\s\S]*?overflow:\s*hidden;/u)
    expect(styleSource).toMatch(/\.commandDeckRegion \{[\s\S]*?display:\s*flex;[\s\S]*?min-height:\s*0;[\s\S]*?overflow:\s*hidden;/u)
    expect(styleSource).not.toMatch(/\.classSelectorRegion \{[\s\S]*?(?:position|z-index|margin):/u)
    expect(styleSource).not.toMatch(/margin:\s*-/u)
    expect(styleSource).not.toContain('overflow-y: auto')
    expect(styleSource).not.toMatch(/position:\s*fixed/u)
    expect(styleSource).not.toMatch(/overviewRegion|gridRegion|workspaceRegion|listRegion|workflowRegion/u)
  })
})
