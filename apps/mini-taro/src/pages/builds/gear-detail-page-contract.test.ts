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

const templateComponentSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/TalentSimulatorComponents.tsx',
), 'utf8')

const componentStyleSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearDetailComponents.module.scss',
), 'utf8')

const editorComponentSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearEditorSheets.tsx',
), 'utf8')

const editorStyleSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/GearEditorSheets.module.scss',
), 'utf8')

const modelSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/gear-detail-model.ts',
), 'utf8')

const commitModelSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.ts',
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
    expect(editorComponentSource).toContain('data-role="gear-editor-scroll"')
    expect(editorComponentSource).toMatch(/<ScrollView[^>]*data-role="gear-editor-scroll"[^>]*scrollY/u)
    expect(editorStyleSource).toMatch(/\.workbenchSheet \{[\s\S]*?position:\s*absolute;[\s\S]*?inset:\s*0;[\s\S]*?overflow:\s*hidden;/u)
    expect(editorStyleSource).not.toMatch(/position:\s*fixed;/u)
    expect(editorStyleSource).not.toMatch(/\b100vh\b/u)
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

  it('keeps candidate and enhancement choices source-owned until explicit apply or confirm', () => {
    expect(editorComponentSource).toContain('data-role="gear-candidate-row"')
    expect(editorComponentSource).toContain('data-role="gear-candidate-variant"')
    expect(editorComponentSource).toContain('data-action-id="gear-candidate-apply"')
    expect(editorComponentSource).toContain('disabled={!canApply || loading}')
    expect(editorComponentSource).toContain('data-role="gear-enhancement-socket"')
    expect(editorComponentSource).toContain('data-action-id="gear-enhancement-confirm"')
    expect(editorComponentSource).not.toContain('resolveSelection')
    expect(editorComponentSource).not.toContain('gearResolve')
  })

  it('locks candidate identity and variant controls while the current Resolve is pending', () => {
    expect(editorComponentSource).toMatch(/function CandidateDetails\(\{[\s\S]*?loading,[\s\S]*?disabled=\{loading \|\| variant\.state === 'blocked'\}/u)
    expect(editorComponentSource).toMatch(/data-role="gear-candidate-row"[\s\S]*?disabled=\{loading\}/u)
    expect(editorComponentSource).toMatch(/<CandidateDetails[\s\S]*?loading=\{loading\}/u)
    expect(pageSource).toMatch(/const chooseCandidate = \(id: string\) => \{[\s\S]*?if \(canonical\.loading\) return[\s\S]*?setCandidateDraft/u)
    expect(pageSource).toMatch(/const chooseCandidateVariant = \(variantKey: string\) => \{[\s\S]*?if \(canonical\.loading\) return[\s\S]*?selectCandidateVariant/u)
    expect(pageSource).toContain('onSelectVariant={chooseCandidateVariant}')
  })

  it('keeps editor choices as drafts until one verified Resolve commits them', () => {
    expect(pageSource).toContain('setCandidateDraft')
    expect(pageSource).toContain('setEnhancementDraft')
    expect(pageSource).toMatch(/const applyCandidateDraft = async \(\)[\s\S]*?await resolveSelection\(/u)
    expect(pageSource).toMatch(/const confirmEnhancementDraft = async \(\)[\s\S]*?await resolveSelection\(/u)
    expect(pageSource).toMatch(/const chooseCandidate = \(id: string\)[\s\S]*?setCandidateDraft/u)
    expect(pageSource).not.toMatch(/const chooseCandidate = async[\s\S]*?await resolveSelection/u)
    expect(pageSource).toMatch(/const chooseEnhancement = \([\s\S]*?setEnhancementDraft/u)
    expect(pageSource).not.toMatch(/const chooseEnhancement = async[\s\S]*?await resolveSelection/u)
    expect(pageSource).toMatch(/const applyCandidateDraft = async \(\)[\s\S]*?await resolveSelection\([\s\S]*?transitionGearEditorCommit\([\s\S]*?if \(!transition\.committed\) return[\s\S]*?setEquipped\(transition\.state\.equipped\)/u)
    expect(pageSource).toMatch(/const confirmEnhancementDraft = async \(\)[\s\S]*?await resolveSelection\([\s\S]*?transitionGearEditorCommit\([\s\S]*?if \(!transition\.committed\) \{[\s\S]*?return[\s\S]*?setEnhancements\(transition\.state\.enhancements\)/u)
    expect(commitModelSource).toContain("if (event.status !== 'resolved')")
    expect(commitModelSource).toContain('return { state, committed: false, reload: false }')
    expect(pageSource.match(/snapshot: resolved\.snapshot/gu)).toHaveLength(2)
    expect(pageSource).not.toContain('resolved.snapshot.selectionIntent ?? resolved.intent')
    expect(pageSource).not.toContain('selection: draft.selection')
  })

  it('discards both editor drafts on conflict and invalidates hydration on every editor boundary', () => {
    expect(pageSource).toMatch(/if \(result\.httpStatus === 409\) \{[\s\S]*?transitionGearEditorCommit\([\s\S]*?status: 'conflict'[\s\S]*?setCandidateDraft\(transition\.state\.candidateDraft\)[\s\S]*?setEnhancementDraft\(transition\.state\.enhancementDraft\)[\s\S]*?void route\.load\(\)/u)
    expect(commitModelSource).toMatch(/if \(event\.status === 'conflict'\) \{[\s\S]*?candidateDraft: null[\s\S]*?enhancementDraft: null[\s\S]*?reload: true/u)
    expect(pageSource).toMatch(/const closeCandidateEditor = \(\) => \{[\s\S]*?candidateRequestId\.current \+= 1[\s\S]*?setCandidateDraft\(null\)[\s\S]*?setEnhancementDraft\(null\)/u)
    expect(pageSource).toMatch(/const reset = \(\) => \{[\s\S]*?candidateRequestId\.current \+= 1[\s\S]*?setCandidateDraft\(null\)[\s\S]*?setEnhancementDraft\(null\)/u)
    expect(pageSource).toMatch(/const importTemplate = async[\s\S]*?candidateRequestId\.current \+= 1[\s\S]*?setCandidateDraft\(null\)[\s\S]*?setEnhancementDraft\(null\)/u)
  })

  it('invalidates an in-flight Resolve before opening another editor or importing', () => {
    const selectionEffect = pageSource.match(/useEffect\(\(\) => \{\n {4}if \(!selectionChanged\.current\)[\s\S]*?\}, \[selectedSpecId, route\.load\]\)/u)?.[0] ?? ''
    expect(selectionEffect).toContain('requestFence.current.replaceDraft()')
    expect(selectionEffect).toContain('setCanonical({ loading: false })')
    expect(pageSource).toMatch(/const openEnhancementGroup = async[\s\S]*?requestFence\.current\.replaceDraft\(\)[\s\S]*?await hydrateSlot/u)
    expect(pageSource).toMatch(/const importTemplate = async[\s\S]*?requestFence\.current\.beginImport\(\)[\s\S]*?setCanonical\(\(current\) => current\.loading/u)
  })

  it('publishes committed and draft identities separately with a canonical resolve marker', () => {
    expect(componentSource).toContain('data-committed-item-id={item.itemId}')
    expect(componentSource).toContain('data-gear-resolve-state={resolveState}')
    expect(componentSource).toContain('data-resolved-slot-item-id={resolvedSlotItemId}')
    expect(componentSource).toContain('data-resolved-slot-variant-key={resolvedSlotVariantKey}')
    expect(componentSource).toContain('data-committed-slot-variant-key={committedSlotVariantKey}')
    expect(editorComponentSource).toContain('data-candidate-item-id={item.itemId}')
    expect(pageSource).toContain("? 'resolving' as const")
    expect(pageSource).toContain('resolvedSlotItemId={resolvedSlotItemId}')
    expect(pageSource).toContain('resolvedSlotVariantKey={resolvedSlotVariantKey}')
    expect(pageSource).toContain('committedSlotVariantKey={committedSlotVariantKey}')
    expect(pageSource).toContain('resolvedSlotIdentity(canonical.snapshot, selectedSlot)')
    expect(pageSource).not.toContain('canonical.snapshot.selectionIntent ?? canonical.intent')
    expect(pageSource).toContain('resolveState={gearResolveState}')
    expect(pageSource).toContain('editor={workbenchEditor}')
  })

  it('hydrates slot editor items from compact group-level enhancement options', () => {
    expect(pageSource).toContain('hydrateCompactSlotGroup(group)')
    expect(pageSource).not.toContain('compact: false')
    expect(pageSource).toMatch(/const hydrateSlot = async[\s\S]*?const group = result\.payload\.replacementCandidates\.find[\s\S]*?hydrateCompactSlotGroup\(group\)[\s\S]*?slotDetailCache\.current\.set\(slot, items\)/u)
  })

  it('rehydrates the committed exact variant through the canonical editor model', () => {
    const exactItemSource = modelSource.match(/function exactHydratedItem\([\s\S]*?\n\}/u)?.[0] ?? ''
    expect(exactItemSource).toContain("const draft = createCandidateDraft('', item)")
    expect(exactItemSource).toContain('selectCandidateVariant(draft, committedVariantKey)')
    expect(exactItemSource).toContain('materializeCandidateDraft')
    expect(exactItemSource).not.toContain("item['variants']")
    expect(modelSource).toMatch(/export function prepareHydratedEnhancementDraft\([\s\S]*?exactHydratedItem\(items, committed\)[\s\S]*?packedEnhancementSelection\(confirmed\)/u)
    expect(pageSource).toContain('prepareHydratedEnhancementDraft(hydrated.items, committedItem, confirmed)')
  })

  it('keeps crafted stats display-only and maps editor actions to draft callbacks', () => {
    const craftedStatSource = editorComponentSource.match(/draft\.craftedStatOptions\.map\(\(item\) => \([\s\S]*?\)\)\}/u)?.[0] ?? ''
    expect(craftedStatSource).toContain('data-role="gear-crafted-stat-display"')
    expect(craftedStatSource).toContain('<View')
    expect(craftedStatSource).not.toContain('<ControlButton')
    expect(craftedStatSource).not.toContain('onClick=')
    expect(craftedStatSource).not.toContain('data-active=')
    expect(editorComponentSource).toContain("onClick={() => onSetGem(socketIndex, '')}")
    expect(editorComponentSource).toContain('onClick={() => onSetGem(socketIndex, item.id)}')
    expect(editorComponentSource.match(/data-socket-index=\{socketIndex\}/gu)).toHaveLength(3)
    expect(editorComponentSource).toMatch(/data-action-id="gear-enhancement-cancel"[^>]*onClick=\{onClose\}/u)
    expect(editorComponentSource).toMatch(/data-action-id="gear-enhancement-confirm"[\s\S]*?onClick=\{onConfirm\}/u)
    expect(editorComponentSource.match(/data-action-id="gear-enhancement-confirm"/gu)).toHaveLength(1)
    expect(pageSource).toContain('socketCount={enhancementSocketCount}')
    expect(editorComponentSource).toContain('按顺序配置')
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

  it('saves complete gear drafts, uses the talent-style import sheet, and clears every equipped slot on reset', () => {
    expect(pageSource).toMatch(/import \{[\s\S]*?communityGearTemplateOptions,[\s\S]*?savedGearTemplateOptions,[\s\S]*?serializeGearTemplateDraft,[\s\S]*?\} from '\.\/gear-template-import-model'/u)
    expect(pageSource).toContain('const communityTemplateOptions = communityGearTemplateOptions(data?.gear.communityTemplates ?? [])')
    expect(pageSource).not.toContain('const communityTemplate = data?.gear.communityTemplates.find')
    expect(pageSource).not.toContain('const savedTemplate = data?.templates.find')
    expect(pageSource).toContain("rawString: serializeGearTemplateDraft({ gearBySlot: equipped, enhancementBySlot: enhancements })")
    expect(pageSource).toContain("const [savedTemplates, setSavedTemplates] = useState<readonly BuildTemplate[]>([])")
    expect(pageSource).toContain("setSavedTemplates(result.payload.templates.filter((template) => template.type === 'gear'))")
    expect(pageSource).toContain("const savedTemplateOptions = savedGearTemplateOptions(savedTemplates, data?.selection.classKey ?? '', data?.selection.specKey ?? '')")
    expect(pageSource).toContain('GearTemplateImportSheet')
    expect(pageSource).toContain('const communityImportItems')
    expect(pageSource).toContain('const savedImportItems')
    expect(pageSource).not.toContain('const importOptions: readonly GearImportSelection[]')
    expect(pageSource).not.toContain('const selected = await chooseActionSheetEntry(importOptions')
    expect(templateComponentSource).toContain('导入装备模板')
    expect(templateComponentSource).toContain('导入此模板')
    expect(pageSource).toContain("setWorkbenchNotice(selection.kind === 'community' ? '已原子导入来源模板' : '已导入已保存模板并重新校验')")
    expect(pageSource).toContain('setEquipped({})')
    expect(pageSource).toContain("setSelectedSlot('')")
    expect(pageSource).toContain('setCandidates([])')
    expect(pageSource).toContain("setStats({ loading: false })")
    expect(pageSource).toContain("disabled: !data || !readiness.selectedCount")
  })
})
