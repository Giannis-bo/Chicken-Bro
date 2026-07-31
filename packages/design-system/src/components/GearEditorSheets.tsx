import { Image, ScrollView, Text, View } from '@tarojs/components'

import type { GearEnhancementSelection, GearItemReference } from '@wow-mini/domain'
import type { ProductionAssetId } from '@wow-mini/assets-manifest'

import { resolveRuntimeMediaUrl } from '../runtime-media'
import { ControlButton } from './ControlButton'
import { SystemGlyph } from './SystemGlyph'
import { useTrustedMediaLoadState } from './useTrustedMediaLoadState'
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

function pairItems<T>(items: readonly T[]): readonly (readonly T[])[] {
  return Array.from(
    { length: Math.ceil(items.length / 2) },
    (_, index) => items.slice(index * 2, index * 2 + 2),
  )
}

function GearEditorMedia({
  iconUrl,
  label,
  className,
  dataRole,
  fallbackAssetId,
  slotId = 'asset_slot.gear-item-object',
}: {
  iconUrl?: string | undefined
  label: string
  className?: string | undefined
  dataRole: string
  fallbackAssetId: ProductionAssetId
  slotId?: string | undefined
}) {
  const trustedUrl = resolveRuntimeMediaUrl(iconUrl)
  const mediaLoadState = useTrustedMediaLoadState(trustedUrl)
  const visible = mediaLoadState.visible
  const mediaState = !trustedUrl ? 'fallback' : mediaLoadState.failed ? 'failed' : mediaLoadState.loaded ? 'loaded' : 'loading'
  return (
    <View
      className={classes(style('editorMedia'), className)}
      data-media-state={mediaState}
      data-media-visible={visible ? 'true' : 'false'}
      data-role={dataRole}
      data-slot-id={slotId}
    >
      <View className={style('editorMediaFallback')}>
        <SystemGlyph assetId={fallbackAssetId} slotId={slotId} />
      </View>
      {trustedUrl ? (
        <Image
          aria-label={label}
          className={classes(style('editorMediaImage'), visible && style('editorMediaImageVisible'))}
          data-loaded={visible ? 'true' : 'false'}
          mode="aspectFill"
          src={trustedUrl}
          onError={mediaLoadState.onError}
          onLoad={mediaLoadState.onLoad}
        />
      ) : null}
    </View>
  )
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
  readonly optionId: string
  readonly label: string
  readonly simcOptions: readonly string[]
  readonly state: 'ready' | 'partial' | 'blocked'
  readonly blockers: readonly string[]
}

/**
 * Structural view of the page-owned GearCandidateDraft. The design system does
 * not own candidate parsing or Resolver materialization.
 */
export interface GearCandidateEditorDraft {
  readonly slot: string
  readonly candidate: GearItemReference
  readonly requiresVariantSelection: boolean
  readonly selectedVariantKey: string
  readonly requiresCraftedStatSelection: boolean
  readonly selectedCraftedOptionId: string
  readonly variants: readonly GearCandidateEditorVariant[]
  readonly craftedStatOptions: readonly GearCandidateEditorCraftedStat[]
}

export function candidateVariantEmptyCopy(
  draft: Pick<GearCandidateEditorDraft, 'requiresVariantSelection' | 'variants'>,
): string {
  return draft.requiresVariantSelection
    ? '后端未返回可校验等级轨道'
    : '此候选无需选择等级轨道'
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
  onSelectCraftedStat: (optionId: string) => void
  onSelectVariant: (variantKey: string) => void
  onApply: () => void
  onClose: () => void
}

function CandidateDetails({
  draft,
  selectedCandidate,
  loading,
  onSelectCraftedStat,
  onSelectVariant,
}: {
  draft: GearCandidateEditorDraft | null
  selectedCandidate: GearCandidateEditorItem | undefined
  loading: boolean
  onSelectCraftedStat: (optionId: string) => void
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
    <View
      className={style('candidateDetails')}
      data-candidate-draft-crafted-option-id={draft.selectedCraftedOptionId}
      data-candidate-draft-item-id={String(draft.candidate.itemId ?? '').trim()}
      data-candidate-draft-variant-key={draft.selectedVariantKey || String(draft.candidate.variantKey ?? '').trim()}
      data-role="gear-candidate-detail"
    >
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
          <Text className={style('sectionEmpty')}>{candidateVariantEmptyCopy(draft)}</Text>
        )}
      </View>

      {draft.craftedStatOptions.length ? (
        <View className={style('section')} data-role="gear-crafted-stats-editor">
          <Text className={style('sectionTitle')}>制造属性</Text>
          <View className={style('craftedStatList')}>
            {draft.craftedStatOptions.map((item) => (
              <ControlButton
                key={item.optionId || item.key || item.label}
                className={classes(
                  style('craftedStat'),
                  item.state !== 'ready' && style('optionControlBlocked'),
                )}
                data-active={draft.selectedCraftedOptionId === item.optionId ? 'true' : 'false'}
                data-crafted-option-id={item.optionId}
                data-role="gear-crafted-stat-option"
                data-state={item.state}
                disabled={loading || item.state !== 'ready'}
                onClick={() => onSelectCraftedStat(item.optionId)}
              >
                <Text>{item.label}</Text>
                <Text>{item.simcOptions.length ? item.simcOptions.join(' · ') : '具体数值由后端校验'}</Text>
                {item.blockers.map((blocker) => <Text key={blocker}>{blocker}</Text>)}
              </ControlButton>
            ))}
          </View>
        </View>
      ) : draft.requiresCraftedStatSelection ? (
        <Text className={style('sectionEmpty')} data-role="gear-crafted-stat-blocked">
          制造属性选项待后端核验
        </Text>
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
  onSelectCraftedStat,
  onSelectVariant,
  onApply,
  onClose,
}: GearCandidateEditorSheetProps) {
  const selectedCandidate = candidates.find((item) => item.id === selectedCandidateId)
  const candidatePairs = pairItems(candidates)
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
              {candidatePairs.map((pair) => {
                const selectedPair = pair.some((item) => item.id === selectedCandidateId)
                return (
                  <View key={pair.map((item) => item.id).join('|')} className={style('candidatePair')} data-role="gear-candidate-pair">
                    {pair.map((item) => {
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
                          <GearEditorMedia
                            className={style('candidateMedia')}
                            dataRole="gear-candidate-media"
                            fallbackAssetId="quick-action-gear-glyph.default"
                            iconUrl={item.iconUrl}
                            label={item.label}
                          />
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
                    {selectedPair ? (
                      <CandidateDetails
                        draft={draft}
                        loading={loading}
                        selectedCandidate={selectedCandidate}
                        onSelectCraftedStat={onSelectCraftedStat}
                        onSelectVariant={onSelectVariant}
                      />
                    ) : null}
                  </View>
                )
              })}
            </View>
          ) : (
            <View className={style('emptyState')}>
              <Text>当前槽位没有可用候选</Text>
            </View>
          )}
          {!loading && candidates.length && !selectedCandidate ? (
            <CandidateDetails
              draft={draft}
              loading={loading}
              selectedCandidate={selectedCandidate}
              onSelectCraftedStat={onSelectCraftedStat}
              onSelectVariant={onSelectVariant}
            />
          ) : null}
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

export interface GearEnhancementEditorItem {
  readonly label: string
  readonly levelLabel: string
  readonly iconUrl?: string | undefined
}

export interface GearEnhancementEditorCompatibleSlot {
  readonly slot: string
  readonly label: string
  readonly item: GearEnhancementEditorItem
  readonly summary: string
  readonly selected: boolean
  readonly disabled?: boolean | undefined
}

export interface GearEnhancementEditorSheetProps {
  slotLabel: string
  item?: GearEnhancementEditorItem | undefined
  draft: GearEnhancementSelection
  socketCount: number
  options: readonly GearEnhancementEditorOption[]
  requestedKind?: GearEnhancementEditorOption['kind'] | undefined
  activeSlot?: string | undefined
  compatibleSlots?: readonly GearEnhancementEditorCompatibleSlot[] | undefined
  canConfirm?: boolean | undefined
  loading?: boolean | undefined
  blockers?: readonly string[] | undefined
  onSelectSlot?: (slot: string) => void
  onSetGem: (socketIndex: number, optionId: string) => void
  onSetSingle: (kind: 'enchant' | 'embellishment', optionId: string) => void
  onConfirm: () => void
  onClose: () => void
}

function enhancementFallbackAssetId(kind: GearEnhancementEditorOption['kind']): ProductionAssetId {
  if (kind === 'socket') return 'gear-enhancement-glyph.gem'
  if (kind === 'enchant') return 'gear-enhancement-glyph.enchant-scroll'
  return 'gear-enhancement-glyph.ornament'
}

function enhancementKindLabel(kind: GearEnhancementEditorOption['kind']): string {
  if (kind === 'socket') return '宝石'
  if (kind === 'enchant') return '附魔'
  return '美化'
}

export interface GearEnhancementSocketRow {
  readonly socketIndex: number
  readonly selectedId: string
  readonly selectable: boolean
}

export function resolveEnhancementSocketRows(
  draft: GearEnhancementSelection,
  socketCount: number,
): readonly GearEnhancementSocketRow[] {
  const capacity = Number.isInteger(socketCount) && socketCount > 0 ? socketCount : 0
  const selectedIds = draft.gemOptionIds.map(displayText).filter(Boolean).slice(0, capacity)
  return Array.from({ length: capacity }, (_, socketIndex) => ({
    socketIndex,
    selectedId: selectedIds[socketIndex] ?? '',
    selectable: socketIndex <= selectedIds.length,
  }))
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
            className={classes(style('optionControl'), style('optionControlEmpty'))}
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
              className={classes(style('optionControl'), style('optionControlWithMedia'))}
              data-active={selectedId === item.id ? 'true' : 'false'}
              data-enhancement-kind={kind}
              data-material-owner="css"
              data-option-id={item.id}
              data-role="gear-enhancement-option"
              data-selection-material={selectedId === item.id ? 'active' : 'inactive'}
              disabled={loading}
              onClick={() => onSetSingle(kind, item.id)}
            >
              <GearEditorMedia
                className={style('enhancementOptionMedia')}
                dataRole="gear-enhancement-option-media"
                fallbackAssetId={enhancementFallbackAssetId(kind)}
                iconUrl={item.iconUrl}
                label={item.label}
                slotId="asset_slot.gear-enhancement-medallions"
              />
              <View className={style('enhancementOptionCopy')}>
                <Text>{item.label}</Text>
                <Text>{selectedId === item.id ? '已选择' : '可选择'}</Text>
              </View>
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
  item,
  draft,
  socketCount,
  options,
  requestedKind,
  activeSlot = '',
  compatibleSlots = [],
  canConfirm = true,
  loading = false,
  blockers = [],
  onSelectSlot,
  onSetGem,
  onSetSingle,
  onConfirm,
  onClose,
}: GearEnhancementEditorSheetProps) {
  const gemOptions = options.filter((item) => item.kind === 'socket')
  const socketRows = resolveEnhancementSocketRows(draft, socketCount)
  const showSocket = !requestedKind || requestedKind === 'socket'
  const showEnchant = !requestedKind || requestedKind === 'enchant'
  const showEmbellishment = !requestedKind || requestedKind === 'embellishment'
  const kindLabel = requestedKind ? enhancementKindLabel(requestedKind) : '强化'
  return (
    <View
      className={style('workbenchSheet')}
      data-active-slot={activeSlot}
      data-blocker-count={blockers.length}
      data-has-item={item ? 'true' : 'false'}
      data-option-count={options.length}
      data-owner="gear-enhancement-editor-sheet"
      data-requested-kind={requestedKind ?? ''}
      data-socket-count={socketCount}
    >
      <View className={style('sheetHeader')}>
        <View>
          <Text>编辑{slotLabel || '装备'}{kindLabel}</Text>
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

          {compatibleSlots.length ? (
            <View className={style('compatibleSlotSection')} data-role="gear-enhancement-compatible-slots">
              <Text className={style('sectionTitle')}>可配置装备</Text>
              <View className={style('compatibleSlotList')}>
                {compatibleSlots.map((slot) => (
                  <ControlButton
                    key={slot.slot}
                    className={style('compatibleSlot')}
                    data-active={slot.selected || slot.slot === activeSlot ? 'true' : 'false'}
                    data-role="gear-enhancement-compatible-slot"
                    data-slot-key={slot.slot}
                    disabled={loading || slot.disabled || !onSelectSlot}
                    onClick={() => onSelectSlot?.(slot.slot)}
                  >
                    <GearEditorMedia
                      className={style('compatibleSlotMedia')}
                      dataRole="gear-enhancement-compatible-slot-media"
                      fallbackAssetId="quick-action-gear-glyph.default"
                      iconUrl={slot.item.iconUrl}
                      label={slot.item.label}
                    />
                    <View className={style('compatibleSlotCopy')}>
                      <Text>{slot.label} · {slot.item.label}</Text>
                      <Text>{slot.summary || slot.item.levelLabel}</Text>
                    </View>
                  </ControlButton>
                ))}
              </View>
            </View>
          ) : null}

          {item ? (
            <View className={style('enhancementItem')} data-role="gear-enhancement-item">
              <GearEditorMedia
                className={style('enhancementItemMedia')}
                dataRole="gear-enhancement-item-media"
                fallbackAssetId="quick-action-gear-glyph.default"
                iconUrl={item.iconUrl}
                label={item.label}
              />
              <View className={style('enhancementItemCopy')}>
                <Text>{item.label}</Text>
                <Text>{item.levelLabel}</Text>
              </View>
            </View>
          ) : null}

          {showSocket ? (
            <>
              {socketRows.length ? (
                <Text className={style('detailMeta')}>宝石按顺序配置；移除前位后，后续宝石会自动前移</Text>
              ) : null}

              {socketRows.map(({ socketIndex, selectedId, selectable }) => (
                <View key={socketIndex} className={style('section')} data-enhancement-kind="socket" data-socket-index={socketIndex}>
                  <Text className={style('sectionTitle')}>宝石插槽 {socketIndex + 1}</Text>
                  <View className={style('optionGrid')}>
                    <ControlButton
                      className={classes(style('optionControl'), style('optionControlEmpty'))}
                      data-active={!selectedId ? 'true' : 'false'}
                      data-material-owner="css"
                      data-role="gear-enhancement-socket"
                      data-selection-material={!selectedId ? 'active' : 'inactive'}
                      data-socket-index={socketIndex}
                      disabled={loading || !selectable}
                      onClick={() => onSetGem(socketIndex, '')}
                    >
                      不镶嵌
                    </ControlButton>
                    {gemOptions.map((item) => (
                      <ControlButton
                        key={`${socketIndex}-${item.id}`}
                        className={classes(style('optionControl'), style('optionControlWithMedia'))}
                        data-active={selectedId === item.id ? 'true' : 'false'}
                        data-material-owner="css"
                        data-option-id={item.id}
                        data-role="gear-enhancement-socket"
                        data-selection-material={selectedId === item.id ? 'active' : 'inactive'}
                        data-socket-index={socketIndex}
                        disabled={loading || !selectable}
                        onClick={() => onSetGem(socketIndex, item.id)}
                      >
                        <GearEditorMedia
                          className={style('enhancementOptionMedia')}
                          dataRole="gear-enhancement-option-media"
                          fallbackAssetId={enhancementFallbackAssetId('socket')}
                          iconUrl={item.iconUrl}
                          label={item.label}
                          slotId="asset_slot.gear-enhancement-medallions"
                        />
                        <View className={style('enhancementOptionCopy')}>
                          <Text>{item.label}</Text>
                          <Text>{selectedId === item.id ? '已镶嵌' : '可镶嵌'}</Text>
                        </View>
                      </ControlButton>
                    ))}
                  </View>
                </View>
              ))}

              {!socketRows.length ? (
                <Text className={style('sectionEmpty')} data-role="gear-enhancement-no-sockets">当前装备没有宝石插槽</Text>
              ) : null}
            </>
          ) : null}

          {showEnchant ? (
            <SingleEnhancementSection
              kind="enchant"
              label="附魔"
              loading={loading}
              options={options}
              selectedId={draft.enchantOptionId}
              onSetSingle={onSetSingle}
            />
          ) : null}
          {showEmbellishment ? (
            <SingleEnhancementSection
              kind="embellishment"
              label="美化"
              loading={loading}
              options={options}
              selectedId={draft.embellishmentOptionId}
              onSetSingle={onSetSingle}
            />
          ) : null}
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
