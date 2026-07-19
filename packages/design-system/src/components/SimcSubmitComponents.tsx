import { Image, Picker, ScrollView, Text, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'
import { resolveRuntimeMediaUrl } from '../runtime-media'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'
import { useTrustedMediaLoadState } from './useTrustedMediaLoadState'

import styles from './SimcSubmitComponents.module.scss'

export interface SimcRecordActionProps {
  onClick: () => void
}

export function SimcRecordAction({ onClick }: SimcRecordActionProps) {
  return (
    <ControlButton className={styles['recordAction'] ?? ''} data-action-id="submission-records" onClick={onClick}>
      <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.simc-header-navigation" />
      <Text>提交记录</Text>
    </ControlButton>
  )
}

export interface SimcSpecializationItem {
  id: string
  label: string
  classLabel: string
  iconUrl?: string | undefined
}

export interface SimcRaceItem {
  id: string
  label: string
}

export interface SimcIdentitySelectorsProps {
  specializations: readonly SimcSpecializationItem[]
  selectedSpecializationId: string
  races: readonly SimcRaceItem[]
  selectedRaceIndex: number
  loading?: boolean | undefined
  disabled?: boolean | undefined
  onSpecializationSelect: (id: string) => void
  onRaceSelect: (index: number) => void
}

function TrustedSpecIcon({ iconUrl }: { iconUrl?: string | undefined }) {
  const trustedUrl = resolveRuntimeMediaUrl(iconUrl)
  const mediaLoadState = useTrustedMediaLoadState(trustedUrl)
  const state = !trustedUrl ? 'fallback' : mediaLoadState.failed ? 'failed' : mediaLoadState.loaded ? 'loaded' : 'loading'
  if (!trustedUrl || mediaLoadState.failed) {
    return (
      <SystemGlyph
        assetId="utility-glyph-family.shield"
        slotId="asset_slot.simc-specialization-media"
      />
    )
  }
  return (
    <Image
      className={styles['specImage'] ?? ''}
      data-media-state={state}
      mode="aspectFit"
      src={trustedUrl}
      onError={mediaLoadState.onError}
      onLoad={mediaLoadState.onLoad}
    />
  )
}

export function SimcIdentitySelectors({
  specializations,
  selectedSpecializationId,
  races,
  selectedRaceIndex,
  loading = false,
  disabled = false,
  onSpecializationSelect,
  onRaceSelect,
}: SimcIdentitySelectorsProps) {
  const visible: readonly SimcSpecializationItem[] = specializations.length ? specializations : Array.from({ length: 6 }, (_, index) => ({
    id: `loading-${index}`,
    label: '读取中',
    classLabel: '职业',
  }))
  return (
    <View
      className={`${styles['identitySelectors'] ?? ''} ${styleSelectorClass('simcIdentitySelectors')}`}
      data-owner="simc-identity-selectors"
      data-region="identity_selectors_panel"
    >
      <View className={styles['specGroup'] ?? ''}>
        <Text className={styles['sectionLabel'] ?? ''}>职业 / 专精</Text>
        <ScrollView className={styles['specScroll'] ?? ''} data-role="simc-spec-scroll" scrollX>
          <View className={styles['specRail'] ?? ''}>
            {visible.map((item) => (
              <ControlButton
                key={item.id}
                className={styles['specOption'] ?? ''}
                aria-label={`${item.classLabel}：${item.label}`}
                data-role="simc-specialization-option"
                data-material-owner="css"
                data-selection-material={item.id === selectedSpecializationId ? 'active' : 'inactive'}
                data-selected={item.id === selectedSpecializationId ? 'true' : 'false'}
                data-spec-id={item.id}
                disabled={disabled || loading || item.id.startsWith('loading-')}
                onClick={() => onSpecializationSelect(item.id)}
              >
                <View className={styles['specMedallion'] ?? ''} data-role="simc-spec-medallion">
                  <TrustedSpecIcon iconUrl={'iconUrl' in item ? item.iconUrl : undefined} />
                </View>
                <Text>{item.label}</Text>
              </ControlButton>
            ))}
          </View>
        </ScrollView>
      </View>
      <View className={styles['raceGroup'] ?? ''}>
        <Text className={styles['sectionLabel'] ?? ''}>支持种族</Text>
        <Picker
          disabled={disabled || loading || races.length === 0}
          mode="selector"
          range={races.map((race) => race.label)}
          value={selectedRaceIndex}
          onChange={(event) => onRaceSelect(Number(event.detail.value))}
        >
          <View className={styles['raceField'] ?? ''} data-selector-id="race">
            <SystemGlyph assetId="utility-glyph-family.user" slotId="asset_slot.simc-selector-affordances" />
            <View>
              <Text>{races[selectedRaceIndex]?.label ?? '未选择'}</Text>
              <Text>列表为当前支持范围</Text>
            </View>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.simc-selector-affordances" />
          </View>
        </Picker>
      </View>
    </View>
  )
}

export interface SimcTemplateSlotProps {
  type: 'talent' | 'gear'
  title: string
  sourceLabel: string
  valueLabel: string
  helperLabel: string
  state: 'ready' | 'partial' | 'blocked' | 'unknown'
  options: readonly string[]
  selectedIndex: number
  loading?: boolean | undefined
  disabled?: boolean | undefined
  onSelect: (index: number) => void
}

export function SimcTemplateSlot({
  type,
  title,
  sourceLabel,
  valueLabel,
  helperLabel,
  state,
  options,
  selectedIndex,
  loading = false,
  disabled = false,
  onSelect,
}: SimcTemplateSlotProps) {
  return (
    <View
      className={`${styles['templateSlot'] ?? ''} ${styleSelectorClass(`simcTemplateSlot${type}`)}`}
      data-owner="simc-template-slot"
      data-region={type === 'talent' ? 'talent_template_panel' : 'gear_template_panel'}
      data-state={state}
      data-template-type={type}
    >
      <View className={styles['templateHeader'] ?? ''}>
        <Text>{title}</Text>
        <Text>{sourceLabel}</Text>
      </View>
      <View className={styles['templateBody'] ?? ''}>
        <View className={styles['templateValue'] ?? ''} data-role="simc-template-value">
          <SystemGlyph
            assetId={type === 'talent' ? 'utility-glyph-family.topic' : 'utility-glyph-family.shield'}
            slotId="asset_slot.simc-template-family"
          />
          <View>
            <Text>{loading ? `正在读取${title}` : valueLabel}</Text>
            <Text>{loading ? '保持模板槽位' : helperLabel}</Text>
          </View>
        </View>
        <Picker
          className={styles['templatePicker'] ?? ''}
          disabled={disabled || loading || options.length === 0}
          mode="selector"
          range={[...options]}
          value={selectedIndex}
          onChange={(event) => onSelect(Number(event.detail.value))}
        >
          <View
            className={styles['templateAction'] ?? ''}
            data-action-id={`select-${type}-template`}
            data-disabled={loading || options.length === 0 ? 'true' : 'false'}
            data-role="simc-template-action"
          >
            <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.simc-template-family" />
            <Text>选择模板</Text>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.simc-selector-affordances" />
          </View>
        </Picker>
      </View>
    </View>
  )
}

export interface SimcScenarioItem {
  id: string
  label: string
}

export interface SimcBuffRuleItem {
  id: string
  label: string
  value: string
  state: 'ready' | 'partial' | 'blocked'
}

export interface SimcCombatConfigurationProps {
  scenarios: readonly SimcScenarioItem[]
  selectedScenarioIndex: number
  durationSeconds?: number | undefined
  buffRules: readonly SimcBuffRuleItem[]
  disabled?: boolean | undefined
  onScenarioSelect: (index: number) => void
}

const sceneGlyphs = [
  'utility-glyph-family.target',
  'utility-glyph-family.group',
  'utility-glyph-family.dungeon',
] as const

const buffGlyphs = [
  'utility-glyph-family.flag',
  'utility-glyph-family.flask',
  'utility-glyph-family.utensils',
  'utility-glyph-family.swords',
] as const

export function SimcCombatConfiguration({
  scenarios,
  selectedScenarioIndex,
  durationSeconds,
  buffRules,
  disabled = false,
  onScenarioSelect,
}: SimcCombatConfigurationProps) {
  return (
    <View
      className={`${styles['combatConfig'] ?? ''} ${styleSelectorClass('simcCombatConfiguration')}`}
      data-owner="simc-combat-configuration"
      data-region="combat_configuration_panel"
    >
      <Text className={styles['configTitle'] ?? ''}>战斗场景</Text>
      <View className={styles['scenarioSegments'] ?? ''}>
        {scenarios.map((scenario, index) => (
          <ControlButton
            key={scenario.id}
            className={`${styles['scenarioOption'] ?? ''} ${styleSelectorClass(`simcScenarioOption${index}`)}`}
            data-role="simc-scenario-option"
            data-material-owner="css"
            data-selection-material={index === selectedScenarioIndex ? 'active' : 'inactive'}
            data-scenario-id={scenario.id}
            data-selected={index === selectedScenarioIndex ? 'true' : 'false'}
            disabled={disabled}
            onClick={() => onScenarioSelect(index)}
          >
            <SystemGlyph assetId={sceneGlyphs[index] ?? 'utility-glyph-family.target'} slotId="asset_slot.simc-scene-family" />
            <Text>{scenario.label}</Text>
          </ControlButton>
        ))}
      </View>
      <View className={styles['durationRow'] ?? ''}>
        <View className={styles['durationLabel'] ?? ''}>
          <SystemGlyph assetId="utility-glyph-family.timer" dataRole="simc-duration-glyph" slotId="asset_slot.simc-duration-control" />
          <Text>战斗时长</Text>
        </View>
        <View
          className={styles['durationField'] ?? ''}
          data-readonly="true"
          data-role="simc-duration-field"
          data-selector-id="duration"
        >
          <Text>{durationSeconds === undefined ? '未返回' : `${durationSeconds} 秒`}</Text>
          <Text>场景固定</Text>
        </View>
      </View>
      <View className={styles['buffHeader'] ?? ''}>
        <Text>战斗增益 (Buff)</Text>
        <View data-disabled="true">
          <SystemGlyph assetId="utility-glyph-family.adjust" slotId="asset_slot.simc-buff-rule-family" />
          <Text>以后端规则为准</Text>
        </View>
      </View>
      <View className={styles['buffRows'] ?? ''}>
        {buffRules.map((rule, index) => (
          <View key={rule.id} className={styles['buffRow'] ?? ''} data-buff-rule-id={rule.id} data-state={rule.state}>
            <SystemGlyph assetId={buffGlyphs[index] ?? 'utility-glyph-family.warning'} slotId="asset_slot.simc-buff-rule-family" />
            <Text>{rule.label}</Text>
            <Text>{rule.value}</Text>
            <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.simc-buff-rule-family" />
          </View>
        ))}
      </View>
    </View>
  )
}

export interface SimcSummaryItem {
  id: string
  label: string
  value: string
  state: 'ready' | 'partial' | 'blocked' | 'unknown'
}

export interface SimcPreSubmitSummaryProps {
  items: readonly SimcSummaryItem[]
}

const summaryGlyphs = [
  'utility-glyph-family.shield',
  'utility-glyph-family.topic',
  'utility-glyph-family.records',
  'utility-glyph-family.adjust',
  'utility-glyph-family.reset',
  'utility-glyph-family.source-link',
] as const

export function SimcPreSubmitSummary({ items }: SimcPreSubmitSummaryProps) {
  return (
    <View
      className={`${styles['summary'] ?? ''} ${styleSelectorClass('simcPreSubmitSummary')}`}
      data-owner="simc-pre-submit-summary"
      data-region="pre_submit_summary_panel"
    >
      <Text className={styles['summaryTitle'] ?? ''}>提交前确认</Text>
      <View className={styles['summaryGrid'] ?? ''}>
        {items.map((item, index) => (
          <View key={item.id} className={styles['summaryRow'] ?? ''} data-state={item.state} data-summary-id={item.id}>
            <SystemGlyph assetId={summaryGlyphs[index] ?? 'utility-glyph-family.document'} slotId="asset_slot.simc-summary-family" />
            <View>
              <Text>{item.label}</Text>
              <Text>{item.value}</Text>
            </View>
            <Text className={styles['statePill'] ?? ''} data-role="simc-summary-state-pill">{item.state === 'ready' ? '就绪' : item.state === 'partial' ? '部分' : item.state === 'blocked' ? '阻断' : '待校验'}</Text>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface SimcBlockerItem {
  id: string
  label: string
  detail: string
  blocked: boolean
}

export interface SimcBlockerPanelProps {
  items: readonly SimcBlockerItem[]
}

export function SimcBlockerPanel({ items }: SimcBlockerPanelProps) {
  const blockerCount = items.filter((item) => item.blocked).length
  return (
    <View
      className={`${styles['blockers'] ?? ''} ${styleSelectorClass('simcBlockerPanel')}`}
      data-blocker-count={blockerCount}
      data-owner="simc-blocker-panel"
      data-region="blocking_warning_panel"
      data-state={blockerCount ? 'blocked' : 'ready'}
    >
      <View className={styles['blockerHeader'] ?? ''}>
        <View className={styles['warningBadge'] ?? ''} data-role="simc-blocker-badge">
          <SystemGlyph assetId={blockerCount ? 'utility-glyph-family.warning' : 'utility-glyph-family.shield'} slotId="asset_slot.simc-blocker-family" />
        </View>
        <View>
          <Text>{blockerCount ? '当前存在阻塞项，暂不能提交' : '当前必填项已通过'}</Text>
          <Text>{blockerCount ? `还有 ${blockerCount} 项需要处理` : '仍需在提交时重新检查活动任务'}</Text>
        </View>
      </View>
      <View className={styles['blockerGrid'] ?? ''}>
        {items.map((item) => (
          <View key={item.id} className={styles['blockerRow'] ?? ''} data-blocker-id={item.id} data-state={item.blocked ? 'blocked' : 'ready'}>
            <View />
            <View>
              <Text>{item.label}</Text>
              <Text>{item.detail}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface SimcSubmissionActionBarProps {
  title: string
  detail: string
  state: 'ready' | 'partial' | 'blocked' | 'unknown'
  canConfirm: boolean
  canSubmit: boolean
  confirming: boolean
  submitting: boolean
  submittedTaskId: string
  onConfirm: () => void
  onSubmit: () => void
  onViewTask: () => void
}

export function SimcSubmissionActionBar({
  title,
  detail,
  state,
  canConfirm,
  canSubmit,
  confirming,
  submitting,
  submittedTaskId,
  onConfirm,
  onSubmit,
  onViewTask,
}: SimcSubmissionActionBarProps) {
  const confirmDisabled = Boolean(submittedTaskId) || !canConfirm || confirming || submitting
  const submitDisabled = !submittedTaskId && (!canSubmit || confirming || submitting)
  return (
    <View
      className={`${styles['submissionBar'] ?? ''} ${styleSelectorClass('simcSubmissionActionBar')}`}
      data-owner="simc-submission-action-bar"
      data-region="submission_action_bar"
      data-state={state}
    >
      <View className={styles['validationState'] ?? ''}>
        <View className={styles['validationIndicator'] ?? ''} data-active={confirming || submitting ? 'true' : 'false'}>
          <SystemGlyph assetId={state === 'blocked' ? 'utility-glyph-family.warning' : 'utility-glyph-family.shield'} slotId="asset_slot.simc-validation-indicator" />
        </View>
        <View>
          <Text data-role="simc-validation-title">{title}</Text>
          <Text data-role="simc-validation-detail">{detail}</Text>
        </View>
      </View>
      <ControlButton
        data-action-id="confirm"
        data-disabled={confirmDisabled ? 'true' : 'false'}
        disabled={confirmDisabled}
        onClick={onConfirm}
      >
        <SystemGlyph assetId="utility-glyph-family.shield" slotId="asset_slot.simc-primary-actions" />
        <Text>{confirming ? '校验中' : '校验组合'}</Text>
      </ControlButton>
      <ControlButton
        className={`${styles['submitAction'] ?? ''} ${submitDisabled ? styles['submitActionDisabled'] ?? '' : ''}`}
        data-action-id={submittedTaskId ? 'view-task' : 'submit'}
        data-disabled={submitDisabled ? 'true' : 'false'}
        disabled={submitDisabled}
        onClick={submittedTaskId ? onViewTask : onSubmit}
      >
        <SystemGlyph
          assetId={submittedTaskId ? 'utility-glyph-family.records' : 'utility-glyph-family.send'}
          slotId="asset_slot.simc-primary-actions"
        />
        <View>
          <Text>{submittedTaskId ? '查看任务' : submitting ? '提交中' : '提交任务'}</Text>
          <Text>{submittedTaskId ? '已返回 taskId' : canSubmit ? '创建真实任务' : '暂不能提交'}</Text>
        </View>
      </ControlButton>
    </View>
  )
}

export interface SimcFooterNoticeProps {
  actionLabel: string
  onAction: () => void
}

export function SimcFooterNotice({ actionLabel, onAction }: SimcFooterNoticeProps) {
  return (
    <View
      className={`${styles['footerNotice'] ?? ''} ${styleSelectorClass('simcFooterNotice')}`}
      data-owner="simc-footer-notice"
      data-region="footer_notice_row"
    >
      <View>
        <View className={styles['footerGlyph'] ?? ''} data-role="simc-footer-glyph">
          <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.simc-footer-utilities" />
        </View>
        <Text>确认只校验输入；真实结果需在任务完成后查看</Text>
      </View>
      <ControlButton data-action-id="task-rules" data-role="simc-footer-action" onClick={onAction}>
        <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.simc-footer-utilities" />
        <Text>{actionLabel}</Text>
        <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.simc-footer-utilities" />
      </ControlButton>
    </View>
  )
}
