import { ScrollView, Text, View } from '@tarojs/components'

import type { GearEnhancementSelection, GearItemReference } from '@wow-mini/domain'

import { ControlButton } from './ControlButton'
import styles from './GearEditorSheets.module.scss'

function style(name: string): string {
  return styles[name] ?? ''
}

function classes(...values: readonly (string | false | null | undefined)[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}

function displayText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function displayStrings(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.map(displayText).filter(Boolean) : []
}

export interface GearCandidateEditorVariant {
  readonly key: string
  readonly label: string
  readonly difficultyLabel: string
  readonly ilevel: number | null
  readonly state: 'ready' | 'partial' | 'blocked'
  readonly blockers: readonly string[]
}

export interface GearCandidateEditorCraftedStat {
  readonly key: string
  readonly label: string
  readonly simcOptions: readonly string[]
}

/**
 * Structural view of the page-owned GearCandidateDraft. The design system does
 * not own candidate parsing or Resolver materialization.
 */
export interface GearCandidateEditorDraft {
  readonly slot: string
  readonly candidate: GearItemReference
  readonly selectedVariantKey: string
  readonly variants: readonly GearCandidateEditorVariant[]
  readonly craftedStatOptions: readonly GearCandidateEditorCraftedStat[]
}

export interface GearCandidateEditorItem {
  readonly id: string
  readonly itemId: string
  readonly label: string
  readonly levelLabel: string
  readonly sourceLabel: string
  readonly statSummary: string
  readonly badgeLabels: readonly string[]
  readonly iconUrl?: string | undefined
  readonly state: 'ready' | 'partial' | 'blocked'
}

export interface GearCandidateEditorSheetProps {
  slotLabel: string
  candidates: readonly GearCandidateEditorItem[]
  selectedCandidateId: string
  draft: GearCandidateEditorDraft | null
  canApply: boolean
  loading?: boolean | undefined
  notice?: string | undefined
  onSelectCandidate: (candidateId: string) => void
  onSelectVariant: (variantKey: string) => void
  onApply: () => void
  onClose: () => void
}

function CandidateDetails({
  draft,
  selectedCandidate,
  loading,
  onSelectVariant,
}: {
  draft: GearCandidateEditorDraft | null
  selectedCandidate: GearCandidateEditorItem | undefined
  loading: boolean
  onSelectVariant: (variantKey: string) => void
}) {
  if (!draft || !selectedCandidate) {
    return (
      <View className={style('emptyState')} data-role="gear-candidate-detail-empty">
        <Text>选择候选后查看来源、属性与合法等级轨道</Text>
      </View>
    )
  }

  const candidateBlockers = displayStrings(draft.candidate['blockers'])
  return (
    <View className={style('candidateDetails')} data-role="gear-candidate-detail">
      <View className={style('detailHeading')}>
        <Text>{selectedCandidate.label}</Text>
        <Text>{selectedCandidate.levelLabel}</Text>
      </View>
      <Text className={style('detailMeta')}>{selectedCandidate.sourceLabel}</Text>
      <Text className={style('detailSummary')}>{selectedCandidate.statSummary}</Text>
      {selectedCandidate.badgeLabels.length ? (
        <View className={style('badgeRow')}>
          {selectedCandidate.badgeLabels.map((label) => <Text key={label}>{label}</Text>)}
        </View>
      ) : null}
      {candidateBlockers.length ? (
        <View className={style('blockerGroup')} data-role="gear-candidate-blockers">
          {candidateBlockers.map((blocker) => <Text key={blocker}>{blocker}</Text>)}
        </View>
      ) : null}

      <View className={style('section')}>
        <Text className={style('sectionTitle')}>合法等级轨道</Text>
        {draft.variants.length ? (
          <View className={style('optionGrid')}>
            {draft.variants.map((variant) => {
              const selected = draft.selectedVariantKey === variant.key
              return (
                <ControlButton
                  key={variant.key}
                  className={classes(style('optionControl'), variant.state === 'blocked' && style('optionControlBlocked'))}
                  data-active={selected ? 'true' : 'false'}
                  data-role="gear-candidate-variant"
                  data-state={variant.state}
                  data-variant-key={variant.key}
                  disabled={loading || variant.state === 'blocked'}
                  onClick={() => onSelectVariant(variant.key)}
                >
                  <Text>{variant.difficultyLabel || variant.label}</Text>
                  <Text>{variant.ilevel === null ? '装等待核验' : `装等 ${Math.round(variant.ilevel)}`}</Text>
                  {variant.blockers.map((blocker) => <Text key={blocker}>{blocker}</Text>)}
                </ControlButton>
              )
            })}
          </View>
        ) : (
          <Text className={style('sectionEmpty')}>后端未返回可校验等级轨道</Text>
        )}
      </View>

      {draft.craftedStatOptions.length ? (
        <View className={style('section')} data-role="gear-crafted-stats-display">
          <Text className={style('sectionTitle')}>制造属性（仅展示）</Text>
          <View className={style('craftedStatList')}>
            {draft.craftedStatOptions.map((item) => (
              <View key={item.key || item.label} className={style('craftedStat')} data-role="gear-crafted-stat-display">
                <Text>{item.label}</Text>
                <Text>{item.simcOptions.length ? item.simcOptions.join(' · ') : '具体数值由后端校验'}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  )
}

export function GearCandidateEditorSheet({
  slotLabel,
  candidates,
  selectedCandidateId,
  draft,
  canApply,
  loading = false,
  notice = '',
  onSelectCandidate,
  onSelectVariant,
  onApply,
  onClose,
}: GearCandidateEditorSheetProps) {
  const selectedCandidate = candidates.find((item) => item.id === selectedCandidateId)
  return (
    <View className={style('workbenchSheet')} data-owner="gear-candidate-editor-sheet" data-slot-key={draft?.slot ?? ''}>
      <View className={style('sheetHeader')}>
        <View>
          <Text>选择{slotLabel || '装备'}</Text>
          <Text>{loading ? '读取候选中' : `${candidates.length} 个候选`}</Text>
        </View>
        <ControlButton className={style('closeControl')} data-action-id="gear-candidate-close" onClick={onClose}>
          取消
        </ControlButton>
      </View>

      <ScrollView className={style('sheetScroll')} data-role="gear-editor-scroll" enhanced scrollY showScrollbar={false}>
        <View className={style('sheetContent')}>
          {notice ? <Text className={style('notice')} data-role="gear-editor-notice">{notice}</Text> : null}
          {loading ? (
            <View className={style('skeletonList')} data-role="gear-candidate-loading">
              {Array.from({ length: 4 }, (_, index) => <View key={index} />)}
            </View>
          ) : candidates.length ? (
            <View className={style('candidateList')}>
              {candidates.map((item) => {
                const selected = item.id === selectedCandidateId
                return (
                  <ControlButton
                    key={item.id}
                    className={classes(style('candidateRow'), item.state === 'blocked' && style('candidateRowBlocked'))}
                    data-active={selected ? 'true' : 'false'}
                    data-candidate-id={item.id}
                    data-candidate-item-id={item.itemId}
                    data-role="gear-candidate-row"
                    data-state={item.state}
                    disabled={loading}
                    onClick={() => onSelectCandidate(item.id)}
                  >
                    <View className={style('candidateCopy')}>
                      <View>
                        <Text>{item.label}</Text>
                        <Text>{item.levelLabel}</Text>
                      </View>
                      <Text>{item.statSummary}</Text>
                      <Text>{item.sourceLabel}</Text>
                    </View>
                  </ControlButton>
                )
              })}
            </View>
          ) : (
            <View className={style('emptyState')}>
              <Text>当前槽位没有可用候选</Text>
            </View>
          )}
          <CandidateDetails
            draft={draft}
            loading={loading}
            selectedCandidate={selectedCandidate}
            onSelectVariant={onSelectVariant}
          />
        </View>
      </ScrollView>

      <View className={style('sheetFooter')}>
        <ControlButton
          className={style('primaryControl')}
          data-action-id="gear-candidate-apply"
          data-role="gear-candidate-apply"
          disabled={!canApply || loading}
          onClick={onApply}
        >
          {loading ? '处理中' : '应用装备'}
        </ControlButton>
      </View>
    </View>
  )
}

export interface GearEnhancementEditorOption {
  readonly id: string
  readonly kind: 'socket' | 'enchant' | 'embellishment'
  readonly label: string
  readonly iconUrl?: string | undefined
  readonly selected: boolean
}

export interface GearEnhancementEditorSheetProps {
  slotLabel: string
  draft: GearEnhancementSelection
  options: readonly GearEnhancementEditorOption[]
  canConfirm?: boolean | undefined
  loading?: boolean | undefined
  blockers?: readonly string[] | undefined
  onSetGem: (socketIndex: number, optionId: string) => void
  onSetSingle: (kind: 'enchant' | 'embellishment', optionId: string) => void
  onConfirm: () => void
  onClose: () => void
}

function SingleEnhancementSection({
  kind,
  label,
  selectedId,
  options,
  loading,
  onSetSingle,
}: {
  kind: 'enchant' | 'embellishment'
  label: string
  selectedId: string
  options: readonly GearEnhancementEditorOption[]
  loading: boolean
  onSetSingle: (kind: 'enchant' | 'embellishment', optionId: string) => void
}) {
  const matching = options.filter((item) => item.kind === kind)
  return (
    <View className={style('section')} data-enhancement-kind={kind}>
      <Text className={style('sectionTitle')}>{label}</Text>
      {matching.length ? (
        <View className={style('optionGrid')}>
          <ControlButton
            className={style('optionControl')}
            data-active={!selectedId ? 'true' : 'false'}
            data-enhancement-kind={kind}
            data-material-owner="css"
            data-role="gear-enhancement-option"
            data-selection-material={!selectedId ? 'active' : 'inactive'}
            disabled={loading}
            onClick={() => onSetSingle(kind, '')}
          >
            不选择
          </ControlButton>
          {matching.map((item) => (
            <ControlButton
              key={item.id}
              className={style('optionControl')}
              data-active={selectedId === item.id ? 'true' : 'false'}
              data-enhancement-kind={kind}
              data-material-owner="css"
              data-option-id={item.id}
              data-role="gear-enhancement-option"
              data-selection-material={selectedId === item.id ? 'active' : 'inactive'}
              disabled={loading}
              onClick={() => onSetSingle(kind, item.id)}
            >
              {item.label}
            </ControlButton>
          ))}
        </View>
      ) : (
        <Text className={style('sectionEmpty')}>当前装备没有可选{label}</Text>
      )}
    </View>
  )
}

export function GearEnhancementEditorSheet({
  slotLabel,
  draft,
  options,
  canConfirm = true,
  loading = false,
  blockers = [],
  onSetGem,
  onSetSingle,
  onConfirm,
  onClose,
}: GearEnhancementEditorSheetProps) {
  const gemOptions = options.filter((item) => item.kind === 'socket')
  return (
    <View className={style('workbenchSheet')} data-owner="gear-enhancement-editor-sheet">
      <View className={style('sheetHeader')}>
        <View>
          <Text>编辑{slotLabel || '装备'}强化</Text>
          <Text>取消不会改变已确认装备</Text>
        </View>
        <ControlButton className={style('closeControl')} data-action-id="gear-enhancement-cancel" onClick={onClose}>
          取消
        </ControlButton>
      </View>

      <ScrollView className={style('sheetScroll')} data-role="gear-editor-scroll" enhanced scrollY showScrollbar={false}>
        <View className={style('sheetContent')}>
          {blockers.length ? (
            <View className={style('blockerGroup')} data-role="gear-enhancement-blockers">
              {blockers.map((blocker) => <Text key={blocker}>{blocker}</Text>)}
            </View>
          ) : null}

          {draft.gemOptionIds.map((selectedId, socketIndex) => (
            <View key={socketIndex} className={style('section')} data-socket-index={socketIndex}>
              <Text className={style('sectionTitle')}>宝石插槽 {socketIndex + 1}</Text>
              <View className={style('optionGrid')}>
                <ControlButton
                  className={style('optionControl')}
                  data-active={!selectedId ? 'true' : 'false'}
                  data-material-owner="css"
                  data-role="gear-enhancement-socket"
                  data-selection-material={!selectedId ? 'active' : 'inactive'}
                  data-socket-index={socketIndex}
                  disabled={loading}
                  onClick={() => onSetGem(socketIndex, '')}
                >
                  不镶嵌
                </ControlButton>
                {gemOptions.map((item) => (
                  <ControlButton
                    key={`${socketIndex}-${item.id}`}
                    className={style('optionControl')}
                    data-active={selectedId === item.id ? 'true' : 'false'}
                    data-material-owner="css"
                    data-option-id={item.id}
                    data-role="gear-enhancement-socket"
                    data-selection-material={selectedId === item.id ? 'active' : 'inactive'}
                    data-socket-index={socketIndex}
                    disabled={loading}
                    onClick={() => onSetGem(socketIndex, item.id)}
                  >
                    {item.label}
                  </ControlButton>
                ))}
              </View>
            </View>
          ))}

          {!draft.gemOptionIds.length ? (
            <Text className={style('sectionEmpty')} data-role="gear-enhancement-no-sockets">当前装备没有宝石插槽</Text>
          ) : null}

          <SingleEnhancementSection
            kind="enchant"
            label="附魔"
            loading={loading}
            options={options}
            selectedId={draft.enchantOptionId}
            onSetSingle={onSetSingle}
          />
          <SingleEnhancementSection
            kind="embellishment"
            label="美化"
            loading={loading}
            options={options}
            selectedId={draft.embellishmentOptionId}
            onSetSingle={onSetSingle}
          />
        </View>
      </ScrollView>

      <View className={style('sheetFooter')}>
        <ControlButton
          className={style('primaryControl')}
          data-action-id="gear-enhancement-confirm"
          data-role="gear-enhancement-confirm"
          disabled={!canConfirm || loading || blockers.length > 0}
          onClick={onConfirm}
        >
          {loading ? '处理中' : '确认强化'}
        </ControlButton>
      </View>
    </View>
  )
}
