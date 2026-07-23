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
    expect(styleSource).toMatch(/\.loadoutSummaryRegion \{[\s\S]*?top:\s*47px;[\s\S]*?height:\s*163px;/u)
    expect(styleSource).toMatch(/\.enhancementRegion \{[\s\S]*?top:\s*216px;[\s\S]*?height:\s*44px;/u)
    expect(styleSource).toMatch(/\.workbenchRegion \{[\s\S]*?top:\s*267px;[\s\S]*?height:\s*427px;/u)
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
    expect(componentStyleSource).not.toContain('.workbenchCenter')
    expect(componentStyleSource).toMatch(/\.candidatePanel \{[\s\S]*?bottom:\s*7px;/u)
  })

  it('uses the entire workbench for two enlarged equipment columns without a center placeholder', () => {
    expect(componentSource).toContain("const leftSlotOrder = ['head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'main_hand', 'off_hand']")
    expect(componentSource).toContain("const rightSlotOrder = ['hands', 'waist', 'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2']")
    expect(componentSource).not.toContain('workbenchCenter')
    expect(componentSource).not.toContain('gear-character-backdrop')
    expect(componentStyleSource).toMatch(/\.slotColumn \{[\s\S]*?display:\s*grid;[\s\S]*?width:\s*calc\(50% - 9px\);[\s\S]*?grid-auto-rows:\s*minmax\(0, 1fr\);/u)
    expect(componentStyleSource).toMatch(/\.slotRow \{[\s\S]*?width:\s*100%;[\s\S]*?grid-template-columns:\s*36px minmax\(0, 1fr\);/u)
    expect(componentStyleSource).not.toContain('max-width: none')
    expect(componentStyleSource).toMatch(/\.slotMedia \{[\s\S]*?width:\s*36px;[\s\S]*?height:\s*36px;/u)
  })

  it('wires every canonical profession to a class launch before reloading the gear workbench', () => {
    expect(pageSource).toMatch(/const classItems:[\s\S]*?data\?\.home\.classOptions[\s\S]*?\.filter\([\s\S]*?\.map\(/u)
    expect(pageSource).toContain('selectBuildsHomeClass(item.id)')
    expect(pageSource).toContain('resolveBuildsHomeLaunch(data.home, nextContext)')
    expect(pageSource).toMatch(/<GearProfessionSelector[\s\S]*?onSelect=\{selectProfession\}/u)
  })

  it('renders icon-bearing profession and specialization dropdowns in one compact row', () => {
    expect(pageSource).toContain('const selectedClassIndex = Math.max(0, classItems.findIndex((item) => item.selected))')
    expect(pageSource).toContain('selectedIndex={selectedClassIndex}')
    expect(pageSource).toContain('value={selectedClassLabel}')
    expect(pageSource).toMatch(/const specItems:[\s\S]*?specIconUrl[\s\S]*?iconUrl/u)
    expect(componentSource).toMatch(/export function GearProfessionSelector[\s\S]*?<Picker[\s\S]*?data-role="gear-profession-field"/u)
    expect(componentSource).toContain('data-role="gear-specialization-field"')
    expect(componentSource).not.toContain('data-role="gear-profession-track"')
    expect(componentStyleSource).toMatch(/\.professionOwner,\n\.specializationOwner \{[\s\S]*?grid-template-columns:\s*22px minmax\(0, 1fr\);/u)
    expect(styleSource).toMatch(/\.professionRegion \{[\s\S]*?height:\s*30px;/u)
    expect(styleSource).toMatch(/\.specializationRegion \{[\s\S]*?height:\s*30px;/u)
    expect(styleSource).toMatch(/\.loadoutSummaryRegion \{[\s\S]*?top:\s*47px;/u)
    expect(styleSource).toMatch(/\.workbenchRegion \{[\s\S]*?top:\s*267px;[\s\S]*?height:\s*427px;/u)
  })

  it('saves complete gear drafts, asks before importing, and clears every equipped slot on reset', () => {
    expect(pageSource).toMatch(/import \{[\s\S]*?communityGearTemplateOptions,[\s\S]*?savedGearTemplateOptions,[\s\S]*?serializeGearTemplateDraft,[\s\S]*?\} from '\.\/gear-template-import-model'/u)
    expect(pageSource).toContain('const communityTemplateOptions = communityGearTemplateOptions(data?.gear.communityTemplates ?? [])')
    expect(pageSource).not.toContain('const communityTemplate = data?.gear.communityTemplates.find')
    expect(pageSource).not.toContain('const savedTemplate = data?.templates.find')
    expect(pageSource).toContain("rawString: serializeGearTemplateDraft({ gearBySlot: equipped, enhancementBySlot: enhancements })")
    expect(pageSource).toContain("const [savedTemplates, setSavedTemplates] = useState<readonly BuildTemplate[]>([])")
    expect(pageSource).toContain("setSavedTemplates(result.payload.templates.filter((template) => template.type === 'gear'))")
    expect(pageSource).toContain("const savedTemplateOptions = savedGearTemplateOptions(savedTemplates, data?.selection.classKey ?? '', data?.selection.specKey ?? '')")
    expect(pageSource).toContain('const importOptions: readonly GearImportSelection[]')
    expect(pageSource).toContain("const selected = await chooseActionSheetEntry(importOptions, (entry) => `${entry.kind === 'community' ? '社区 · ' : '已保存 · '}${entry.label}`)")
    expect(pageSource).toContain("setWorkbenchNotice(selection.kind === 'community' ? '已原子导入来源模板' : '已导入已保存模板并重新校验')")
    expect(pageSource).toContain('setEquipped({})')
    expect(pageSource).toContain("setSelectedSlot('')")
    expect(pageSource).toContain('setCandidates([])')
    expect(pageSource).toContain("setStats({ loading: false })")
    expect(pageSource).toContain("disabled: !data || !readiness.selectedCount")
  })
})
