import { Text, View } from '@tarojs/components'

import type { BuildTemplate } from '@wow-mini/domain'

import { ActionButton } from './ActionButton'
import { StatusVisual } from './StatusVisual'
import { SystemGlyph } from './SystemGlyph'
import { ownerClass, ownerStyle } from './style'

export interface TemplateLibraryProps {
  templates: readonly BuildTemplate[]
  emptyText: string
  selectionMode?: boolean
  assetMode?: 'none' | 'source' | 'source-and-category' | undefined
  onSelect?: (template: BuildTemplate) => void
  onDelete?: (template: BuildTemplate) => void
}

export function TemplateLibrary({
  templates,
  emptyText,
  selectionMode = false,
  assetMode = 'none',
  onSelect,
  onDelete,
}: TemplateLibraryProps) {
  if (!templates.length) return <View className={ownerStyle('feedEmpty')}>{emptyText}</View>
  return (
    <View className={ownerStyle('templateList')}>
      {templates.map((template) => (
        <View key={template.id} className={ownerStyle('templateRow')} onClick={() => onSelect?.(template)}>
          {assetMode === 'none' ? (
            <StatusVisual compact state={template.remote ? 'ready' : 'stale'} />
          ) : (
            <SystemGlyph
              assetId={template.remote ? 'source-badge-family.verified' : 'source-badge-family.reference'}
              className={ownerClass(
                ownerStyle('templateSourceGlyph'),
                template.remote ? ownerStyle('templateSourceRemote') : ownerStyle('templateSourceLocal'),
              )}
              slotId="asset_slot.source-badge-family"
            />
          )}
          <View className={ownerStyle('templateBody')}>
            <View className={ownerStyle('templateTitleRow')}>
              {assetMode === 'source-and-category' ? (
                <SystemGlyph
                  assetId={template.type === 'talent' ? 'template-talent-medallion.default' : 'utility-glyph-family.records'}
                  className={ownerStyle('templateCategoryGlyph')}
                  slotId={template.type === 'talent' ? 'asset_slot.template-talent-medallion' : 'asset_slot.utility-glyph-family'}
                />
              ) : null}
              <Text className={ownerStyle('templateTitle')}>{template.title}</Text>
            </View>
            <Text className={ownerStyle('templateMeta')}>
              {template.type === 'talent' ? '天赋' : '装备'} · {template.statusLabel} · {template.remote ? '账户同步' : '仅本地'}
            </Text>
          </View>
          {selectionMode && onSelect ? (
            <ActionButton variant="ghost" onClick={() => onSelect(template)}>选择</ActionButton>
          ) : null}
          {!selectionMode && onDelete ? (
            <ActionButton variant="danger" onClick={() => onDelete(template)}>删除</ActionButton>
          ) : null}
        </View>
      ))}
    </View>
  )
}
