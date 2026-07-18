import { Text, View } from '@tarojs/components'

import { assetRuntimePath, type ProductionAssetId } from '@wow-mini/assets-manifest'
import type { ReadinessState } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { ProductionAssetImage } from './ProductionAsset'
import { ForgedPanel } from './ReconstructionPrimitives'
import { SystemGlyph } from './SystemGlyph'
import { StatusVisual } from './StatusVisual'
import { ownerClass, ownerStyle } from './style'
import { styleSelectorClass } from './selector-markers'
import workbenchStyles from './EvidenceLedgerWorkbench.module.scss'

function workbenchLedgerStyle(name: string): string {
  return [workbenchStyles[name] ?? '', styleSelectorClass(`ledger-workbench-${name}`)].filter(Boolean).join(' ')
}

export interface EvidenceLedgerRow {
  id: string
  label: string
  value: string
  state: ReadinessState
  sourceUrl?: string
  actionLabel?: string
  sourceCountLabel?: string | undefined
  blockerCountLabel?: string | undefined
  revisionLabel?: string | undefined
  region?: string | undefined
}

export interface EvidenceLedgerProps {
  rows: readonly EvidenceLedgerRow[]
  emptyText?: string
  variant?: 'ledger' | 'inline' | 'workbench' | 'detail' | undefined
  onSource?: (row: EvidenceLedgerRow) => void
  title?: string | undefined
  region?: string | undefined
}

const fallbackWorkbenchRowGlyph: { assetId: ProductionAssetId; slotId: string } = {
  assetId: 'utility-glyph-family.assistant',
  slotId: 'asset_slot.utility-glyph-family',
}

const workbenchRowGlyphs: Readonly<Record<string, { assetId: ProductionAssetId; slotId: string }>> = {
  talents: { assetId: 'quick-action-talents-glyph.default', slotId: 'asset_slot.quick-action-talents-glyph' },
  gear: { assetId: 'quick-action-gear-glyph.default', slotId: 'asset_slot.quick-action-gear-glyph' },
  simc: { assetId: 'quick-action-simc-glyph.default', slotId: 'asset_slot.quick-action-simc-glyph' },
  assistant: fallbackWorkbenchRowGlyph,
  captain: fallbackWorkbenchRowGlyph,
  scenario: fallbackWorkbenchRowGlyph,
}

export function EvidenceLedger({
  rows,
  emptyText = '暂无可验证证据',
  variant = 'ledger',
  onSource,
  title,
  region = 'shared_evidence-ledger',
}: EvidenceLedgerProps) {
  if (variant === 'detail') {
    return (
      <ForgedPanel
        className={ownerClass(ownerStyle('ledger'), ownerStyle('ledgerDetail'))}
        contentInset={12}
        frameWidth={8}
        interactiveInset={12}
        owner="evidence-ledger"
        region={region}
      >
        <View className={ownerStyle('ledgerDetailHeader')} data-frame-content="true" data-role="ledger-title-bar">
          <View className={ownerStyle('ledgerDetailTitle')}>
            <SystemGlyph assetId="utility-glyph-family.adjust" slotId="asset_slot.utility-glyph-family" />
            <Text>{title ?? '证据明细'}</Text>
          </View>
          <ProductionAssetImage
            alt="证据列表已展开"
            assetId="news-detail-evidence-chevron.expanded"
            className={ownerStyle('ledgerDetailChevron')}
            slotId="asset_slot.news-detail-evidence-chevron"
          />
        </View>
        {rows.length ? (
          <View className={ownerStyle('ledgerDetailList')} data-frame-content="true" data-role="ledger-list">
            {rows.map((row) => (
              <View key={row.id} className={ownerStyle('ledgerDetailRow')} data-role="ledger-row">
                <View className={ownerStyle('ledgerDetailIdentity')}>
                  <Text className={ownerStyle('ledgerDetailLabel')}>{row.label}</Text>
                  <Text className={ownerStyle('ledgerDetailValue')}>{row.value}</Text>
                </View>
                <StatusVisual compact state={row.state} variant="pill" />
                {row.sourceUrl && onSource ? (
                  <ActionButton
                    ariaLabel={`${row.label}来源`}
                    iconPath={assetRuntimePath('utility-glyph-family.copy') ?? undefined}
                    iconSlotId="asset_slot.utility-glyph-family"
                    variant="secondaryMetal"
                    onClick={() => onSource(row)}
                  >
                    {null}
                  </ActionButton>
                ) : <View className={ownerStyle('ledgerDetailActionSpacer')} />}
              </View>
            ))}
          </View>
        ) : (
          <View className={ownerStyle('ledgerDetailEmpty')} data-frame-content="true" data-role="ledger-empty">
            <ProductionAssetImage
              alt="暂无证据"
              assetId="empty-state-emblem.evidence-empty"
              className={ownerStyle('ledgerDetailEmptyEmblem')}
              slotId="asset_slot.empty-state-emblem"
            />
            <Text>{emptyText}</Text>
          </View>
        )}
      </ForgedPanel>
    )
  }
  if (!rows.length) {
    if (variant === 'workbench') {
      return (
        <ForgedPanel
          className={ownerClass(ownerStyle('ledger'), ownerStyle('ledgerWorkbench'), workbenchLedgerStyle('root'))}
          contentInset={6}
          frameAssetId="builds-frame.evidence-list"
          frameSlotId="asset_slot.builds-frame-family"
          frameWidth={8}
          interactiveInset={7}
          owner="evidence-ledger"
          region={region}
        >
          <View
            className={ownerClass(ownerStyle('ledgerWorkbenchTitleBar'), workbenchLedgerStyle('frameContent'))}
            data-frame-content="true"
            data-role="ledger-title-bar"
          >
            <View className={ownerStyle('ledgerWorkbenchTitleIdentity')}>
              <SystemGlyph
                assetId="utility-glyph-family.adjust"
                className={ownerStyle('ledgerWorkbenchScale')}
                slotId="asset_slot.utility-glyph-family"
              />
              <Text className={ownerStyle('ledgerTitle')}>{title ?? 'EvidenceLedger'}</Text>
            </View>
          </View>
          <View
            className={ownerClass(ownerStyle('ledgerWorkbenchEmpty'), workbenchLedgerStyle('frameContent'))}
            data-frame-content="true"
          >{emptyText}</View>
        </ForgedPanel>
      )
    }
    return (
      <View
        className={ownerStyle('ledger')}
        data-owner="evidence-ledger"
        data-region={region}
      >
        {title ? <Text className={ownerStyle('ledgerTitle')}>{title}</Text> : null}
        <View className={ownerStyle('feedEmpty')}>{emptyText}</View>
      </View>
    )
  }
  const marker = variant === 'inline'
    ? { assetId: 'source-badge-family.information', slotId: 'asset_slot.source-badge-family' } as const
    : { assetId: 'utility-glyph-family.document', slotId: 'asset_slot.utility-glyph-family' } as const
  if (variant === 'workbench') {
    return (
      <ForgedPanel
        className={ownerClass(ownerStyle('ledger'), ownerStyle('ledgerWorkbench'), workbenchLedgerStyle('root'))}
        contentInset={6}
        frameAssetId="builds-frame.evidence-list"
        frameSlotId="asset_slot.builds-frame-family"
        frameWidth={8}
        interactiveInset={7}
        owner="evidence-ledger"
        region={region}
      >
        <View
          className={ownerClass(ownerStyle('ledgerWorkbenchTitleBar'), workbenchLedgerStyle('frameContent'))}
          data-frame-content="true"
          data-role="ledger-title-bar"
        >
          <View className={ownerStyle('ledgerWorkbenchTitleIdentity')}>
            <SystemGlyph
              assetId="utility-glyph-family.adjust"
              className={ownerStyle('ledgerWorkbenchScale')}
              slotId="asset_slot.utility-glyph-family"
              />
              <Text className={ownerStyle('ledgerTitle')}>{title ?? 'EvidenceLedger'}</Text>
          </View>
          <View className={ownerStyle('ledgerWorkbenchColumnBand')} data-role="ledger-column-band">
            <View className={ownerStyle('ledgerWorkbenchColumnHeading')}>
              <SystemGlyph
                assetId="utility-glyph-family.source-link"
                className={ownerStyle('ledgerWorkbenchColumnGlyph')}
                slotId="asset_slot.utility-glyph-family"
              />
              <Text className={ownerStyle('ledgerWorkbenchColumnLabel')}>来源</Text>
            </View>
            <View className={ownerStyle('ledgerWorkbenchColumnHeading')}>
              <SystemGlyph
                assetId="utility-glyph-family.warning"
                className={ownerStyle('ledgerWorkbenchColumnGlyph')}
                slotId="asset_slot.utility-glyph-family"
              />
              <Text className={ownerStyle('ledgerWorkbenchColumnLabel')}>阻断</Text>
            </View>
            <View className={ownerStyle('ledgerWorkbenchColumnHeading')}>
              <SystemGlyph
                assetId="utility-glyph-family.reset"
                className={ownerStyle('ledgerWorkbenchColumnGlyph')}
                slotId="asset_slot.utility-glyph-family"
              />
              <Text className={ownerStyle('ledgerWorkbenchColumnLabel')}>修订</Text>
            </View>
          </View>
          <View className={ownerStyle('ledgerWorkbenchColumnSpacer')} />
        </View>
        <View
          className={ownerClass(ownerStyle('ledgerWorkbenchList'), workbenchLedgerStyle('frameContent'))}
          data-frame-content="true"
          data-role="ledger-list"
        >
          {rows.map((row) => {
            const rowGlyph = workbenchRowGlyphs[row.id] ?? fallbackWorkbenchRowGlyph
            return (
              <View
                key={row.id}
                className={ownerStyle('ledgerWorkbenchRow')}
                data-layout="ledger-list-item"
                data-region={row.region}
                data-role="ledger-row"
              >
                <View
                  className={ownerClass(ownerStyle('ledgerWorkbenchRowBody'), workbenchLedgerStyle('frameContent'))}
                  data-frame-content="true"
                >
                  <View className={ownerStyle('ledgerWorkbenchIdentity')}>
                    <View className={ownerStyle('ledgerWorkbenchRowIcon')} data-role="ledger-row-icon">
                      <SystemGlyph assetId={rowGlyph.assetId} slotId={rowGlyph.slotId} />
                    </View>
                    <View className={ownerStyle('ledgerWorkbenchIdentityCopy')}>
                      <Text className={ownerStyle('ledgerLabel')}>{row.label}</Text>
                      <Text className={ownerStyle('ledgerWorkbenchRowValue')}>{row.value}</Text>
                    </View>
                  </View>
                  <View className={ownerStyle('ledgerWorkbenchFactBand')} data-role="ledger-fact-band">
                    <View
                      className={ownerClass(ownerStyle('ledgerWorkbenchFact'), workbenchLedgerStyle('factSource'))}
                      data-fact-kind="source"
                      data-role="ledger-fact"
                    >
                      <SystemGlyph
                        assetId="utility-glyph-family.source-link"
                        className={ownerStyle('ledgerWorkbenchFactGlyph')}
                        slotId="asset_slot.utility-glyph-family"
                      />
                      <Text>{row.sourceCountLabel?.replace(/^来源\s*/, '') ?? '--'}</Text>
                    </View>
                    <View
                      className={ownerClass(ownerStyle('ledgerWorkbenchFact'), workbenchLedgerStyle('factBlocker'))}
                      data-fact-kind="blocker"
                      data-role="ledger-fact"
                    >
                      <SystemGlyph
                        assetId="utility-glyph-family.warning"
                        className={ownerStyle('ledgerWorkbenchFactGlyph')}
                        slotId="asset_slot.utility-glyph-family"
                      />
                      <Text>{row.blockerCountLabel?.replace(/^阻断\s*/, '') ?? '--'}</Text>
                    </View>
                    <View
                      className={ownerClass(
                        ownerStyle('ledgerWorkbenchFact'),
                        ownerStyle('ledgerRevision'),
                        workbenchLedgerStyle('factRevision'),
                      )}
                      data-fact-kind="revision"
                      data-role="ledger-fact"
                    >
                      <SystemGlyph
                        assetId="utility-glyph-family.reset"
                        className={ownerStyle('ledgerWorkbenchFactGlyph')}
                        slotId="asset_slot.utility-glyph-family"
                      />
                      <Text>{row.revisionLabel ?? '待核验'}</Text>
                    </View>
                  </View>
                  <View className={ownerStyle('ledgerWorkbenchAction')} data-role="ledger-row-action">
                    <ActionButton
                      ariaLabel={`进入${row.label}`}
                      iconPath={assetRuntimePath('utility-glyph-family.chevron-right') ?? undefined}
                      iconSlotId="asset_slot.utility-glyph-family"
                      variant="secondaryMetal"
                      onClick={() => onSource?.(row)}
                    >
                      {row.actionLabel ?? '进入'}
                    </ActionButton>
                  </View>
                </View>
              </View>
            )
          })}
        </View>
      </ForgedPanel>
    )
  }
  return (
    <View
      className={ownerClass(
        ownerStyle('ledger'),
        variant === 'inline' && ownerStyle('ledgerInline'),
      )}
      data-owner="evidence-ledger"
      data-region={region}
    >
      {title ? <Text className={ownerStyle('ledgerTitle')}>{title}</Text> : null}
      {rows.map((row) => (
        <View key={row.id} className={ownerStyle('ledgerRow')} data-region={row.region}>
          <SystemGlyph
            assetId={marker.assetId}
            className={ownerStyle('ledgerMarker')}
            slotId={marker.slotId}
          />
          <View className={ownerStyle('ledgerContent')}>
            <Text className={ownerStyle('ledgerLabel')}>{row.label}</Text>
            <Text className={ownerStyle('ledgerValue')}>{row.value}</Text>
            <StatusVisual compact state={row.state} />
          </View>
          {row.sourceUrl && onSource ? (
            <ActionButton
              iconPath={assetRuntimePath('utility-glyph-family.source-link') ?? undefined}
              iconSlotId="asset_slot.utility-glyph-family"
              variant="ghost"
              onClick={() => onSource(row)}
            >
              {row.actionLabel ?? '来源'}
            </ActionButton>
          ) : null}
        </View>
      ))}
    </View>
  )
}
