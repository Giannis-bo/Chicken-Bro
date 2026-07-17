import { Image, Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'

import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { ControlButton } from './ControlButton'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'

import styles from './ProfileTemplatesComponents.module.scss'

export interface ProfileArchiveMetric {
  id: 'talent' | 'gear' | 'archive'
  label: string
  value: string
}

export interface ProfileSummaryPanelProps {
  avatarUrl: string
  nickname: string
  signature: string
  storageMode: 'local' | 'mixed' | 'account'
  storageModeLabel: string
  syncLabel: string
  metrics: readonly ProfileArchiveMetric[]
  onAvatarEdit: (avatarUrl: string) => void
  onEdit: () => void
}

const metricGlyphs = [
  'utility-glyph-family.topic',
  'utility-glyph-family.shield',
  'utility-glyph-family.records',
] as const

export function ProfileSummaryPanel({
  avatarUrl,
  nickname,
  signature,
  storageMode,
  storageModeLabel,
  syncLabel,
  metrics,
  onAvatarEdit,
  onEdit,
}: ProfileSummaryPanelProps) {
  const [avatarFailed, setAvatarFailed] = useState(false)
  useEffect(() => setAvatarFailed(false), [avatarUrl])
  const showAvatar = Boolean(avatarUrl) && !avatarFailed

  return (
    <View className={`${styles['summary'] ?? ''} ${styleSelectorClass('profileSummary')}`} data-owner="profile-summary-panel" data-mode={storageMode}>
      <View className={styles['identityAction'] ?? ''}>
        <ControlButton
          className={`${styles['avatarAction'] ?? ''} ${styles['interactive'] ?? ''}`}
          data-action-id="edit-avatar"
          openType="chooseAvatar"
          onChooseAvatar={(event) => {
            const avatarUrl = (event.detail as { avatarUrl?: string } | undefined)?.avatarUrl
            if (avatarUrl) onAvatarEdit(avatarUrl)
          }}
        >
          <View className={`${styles['avatar'] ?? ''} ${!showAvatar ? styles['avatarFallback'] ?? '' : ''}`} data-avatar-trusted={showAvatar ? 'true' : 'false'} data-role="profile-avatar-socket">
          {showAvatar ? (
            <Image mode="aspectFit" src={avatarUrl} onError={() => setAvatarFailed(true)} />
          ) : <SystemGlyph assetId="utility-glyph-family.user" slotId="asset_slot.profile-avatar" />}
          </View>
          <Text className={styles['avatarEditLabel'] ?? ''}>更换头像</Text>
        </ControlButton>
        <View className={`${styles['identityCopy'] ?? ''} ${styles['interactive'] ?? ''}`} data-action-id="edit-profile" role="button" onClick={onEdit}>
          <View className={styles['nicknameRow'] ?? ''}>
            <Text data-role="profile-nickname">{nickname}</Text>
            <SystemGlyph assetId="utility-glyph-family.adjust" slotId="asset_slot.profile-edit" />
          </View>
          <Text data-role="profile-signature">{signature}</Text>
          <Text data-role="profile-sync-label">{syncLabel}</Text>
        </View>
        <View className={styles['modeBadge'] ?? ''} data-role="profile-mode-badge">
          <SystemGlyph assetId={storageMode === 'account' ? 'utility-glyph-family.source-link' : 'utility-glyph-family.save'} slotId="asset_slot.profile-mode" />
          <Text data-role="profile-mode-label">{storageModeLabel}</Text>
        </View>
      </View>
      <View className={styles['metrics'] ?? ''} data-count={metrics.length}>
        {metrics.map((metric, index) => (
          <View key={metric.id} data-profile-metric-id={metric.id} data-role="profile-metric-cell">
            <SystemGlyph assetId={metricGlyphs[index] ?? 'utility-glyph-family.records'} slotId="asset_slot.profile-metrics" />
            <View><Text data-role="profile-metric-label">{metric.label}</Text><Text data-role="profile-metric-value">{metric.value}</Text></View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface ProfileTemplateCategory {
  id: 'talent' | 'gear'
  title: string
  description: string
  count: number
}

export interface ProfileTemplateLibraryProps {
  items: readonly ProfileTemplateCategory[]
  onSelect: (id: ProfileTemplateCategory['id']) => void
}

export function ProfileTemplateLibrary({ items, onSelect }: ProfileTemplateLibraryProps) {
  return (
    <View className={`${styles['library'] ?? ''} ${styleSelectorClass('profileTemplateLibrary')}`} data-owner="profile-template-library">
      <Text className={styles['sectionTitle'] ?? ''} data-role="profile-section-title">模板库</Text>
      <View className={styles['categoryGrid'] ?? ''} data-count={items.length}>
        {items.map((item) => (
          <View key={item.id} className={`${styles['interactive'] ?? ''} ${item.id === 'talent' ? styles['categoryTalent'] ?? '' : styles['categoryGear'] ?? ''} ${styleSelectorClass(`profileCategory${item.id}`)}`} data-action-id={`open-${item.id}`} data-category-id={item.id} data-role="profile-category-card" role="button" onClick={() => onSelect(item.id)}>
            <View className={styles['categoryEmblem'] ?? ''} data-role="profile-category-emblem">
              <ProductionAssetGlyph
                assetId={item.id === 'talent' ? 'template-talent-medallion.default' : 'quick-action-gear-glyph.default'}
                fallbackAssetId={item.id === 'talent' ? 'utility-glyph-family.topic' : 'utility-glyph-family.shield'}
                fallbackSlotId="asset_slot.utility-glyph-family"
                slotId={item.id === 'talent' ? 'asset_slot.template-talent-medallion' : 'asset_slot.quick-action-gear-glyph'}
              />
            </View>
            <View className={styles['categoryCopy'] ?? ''}>
              <Text data-role="profile-category-title">{item.title}</Text>
              <Text data-role="profile-category-description">{item.description}</Text>
              <Text data-role="profile-category-count">{item.count} 项</Text>
            </View>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.profile-categories" />
          </View>
        ))}
      </View>
    </View>
  )
}

export interface ProfileRecentTemplateItem {
  position: number
  id: string
  title: string
  type: 'talent' | 'gear' | 'unavailable'
  typeLabel: string
  savedLabel: string
  sourceLabel: string
  deletable: boolean
  empty: boolean
}

export interface ProfileRecentSavesProps {
  items: readonly ProfileRecentTemplateItem[]
  deletingId: string
  onShowAll: () => void
  onDelete: (id: string) => void
}

export function ProfileRecentSaves({ items, deletingId, onShowAll, onDelete }: ProfileRecentSavesProps) {
  return (
    <View className={`${styles['recent'] ?? ''} ${styleSelectorClass('profileRecentSaves')}`} data-owner="profile-recent-saves" data-region="recent_saves">
      <View className={styles['recentHeading'] ?? ''}>
        <Text className={styles['sectionTitle'] ?? ''} data-role="profile-section-title">最近保存</Text>
        <View className={styles['interactive'] ?? ''} data-action-id="show-all-templates" role="button" onClick={onShowAll}>
          <Text>全部</Text>
          <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.profile-recent" />
        </View>
      </View>
      <View className={styles['recentRows'] ?? ''} data-count={items.length}>
        {items.map((item) => (
          <View key={`recent-${item.position}`} className={`${styles['recentRow'] ?? ''} ${item.empty ? styles['recentRowEmpty'] ?? '' : ''} ${item.type === 'talent' ? styles['recentTalent'] ?? '' : item.type === 'gear' ? styles['recentGear'] ?? '' : styles['recentUnavailable'] ?? ''}`} data-empty={item.empty ? 'true' : 'false'} data-recent-position={item.position}>
            <View className={styles['recentIcon'] ?? ''} data-role="profile-recent-icon">
              {item.type === 'unavailable' ? (
                <SystemGlyph assetId="utility-glyph-family.records" slotId="asset_slot.profile-recent" />
              ) : (
                <ProductionAssetGlyph
                  assetId={item.type === 'talent' ? 'template-talent-medallion.default' : 'quick-action-gear-glyph.default'}
                  fallbackAssetId={item.type === 'talent' ? 'utility-glyph-family.topic' : 'utility-glyph-family.shield'}
                  fallbackSlotId="asset_slot.utility-glyph-family"
                  slotId={item.type === 'talent' ? 'asset_slot.template-talent-medallion' : 'asset_slot.quick-action-gear-glyph'}
                />
              )}
            </View>
            <View className={styles['recentCopy'] ?? ''}>
              <Text data-role="profile-recent-title">{item.title}</Text>
              <View><Text data-role="profile-recent-meta">{item.typeLabel}</Text><Text data-role="profile-recent-meta">{item.sourceLabel}</Text></View>
              <View className={styles['savedChip'] ?? ''}>
                <SystemGlyph assetId="utility-glyph-family.runtime" slotId="asset_slot.profile-recent" />
                <Text data-role="profile-recent-saved-label">{item.savedLabel}</Text>
              </View>
            </View>
            <View
              className={`${styles['interactive'] ?? ''} ${!item.deletable || deletingId === item.id ? styles['deleteDisabled'] ?? '' : ''}`}
              data-action-id={`delete-template-${item.position}`}
              data-disabled={!item.deletable || deletingId === item.id ? 'true' : 'false'}
              data-role="profile-delete-action"
              role="button"
              onClick={() => {
                if (item.deletable && deletingId !== item.id && item.id) onDelete(item.id)
              }}
            >
              <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.profile-recent" />
              <Text data-role="profile-delete-label">
                {!item.deletable ? '不可删除' : deletingId === item.id ? '删除中' : '删除'}
              </Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface ProfileSettingItem {
  id: 'character' | 'preference' | 'source' | 'help'
  label: string
  value: string
}

export interface ProfileSettingsListProps {
  items: readonly ProfileSettingItem[]
  onSelect: (id: ProfileSettingItem['id']) => void
}

const settingGlyphs = [
  'utility-glyph-family.user',
  'utility-glyph-family.shield',
  'utility-glyph-family.records',
  'utility-glyph-family.document',
] as const

export function ProfileSettingsList({ items, onSelect }: ProfileSettingsListProps) {
  return (
    <View className={`${styles['settings'] ?? ''} ${styleSelectorClass('profileSettings')}`} data-owner="profile-settings-list">
      <Text className={styles['sectionTitle'] ?? ''} data-role="profile-section-title">设置与支持</Text>
      <View className={styles['settingRows'] ?? ''} data-count={items.length}>
        {items.map((item, index) => (
          <View key={item.id} className={`${styles['interactive'] ?? ''} ${styles[`setting-${item.id}`] ?? ''}`} data-action-id={`setting-${item.id}`} data-setting-id={item.id} role="button" onClick={() => onSelect(item.id)}>
            <View className={styles['settingIcon'] ?? ''} data-role="profile-setting-icon">
              <SystemGlyph assetId={settingGlyphs[index] ?? 'utility-glyph-family.document'} slotId="asset_slot.profile-settings" />
            </View>
            <Text data-role="profile-setting-label">{item.label}</Text>
            <Text data-role="profile-setting-value">{item.value}</Text>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.profile-settings" />
          </View>
        ))}
      </View>
    </View>
  )
}
