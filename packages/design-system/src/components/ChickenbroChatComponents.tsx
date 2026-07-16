import { Picker, Text, Textarea, View } from '@tarojs/components'

import { ControlButton } from './ControlButton'

import type { ChatMessage } from '@wow-mini/domain'

import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'

import styles from './ChickenbroChatComponents.module.scss'

export interface ChickenbroContextCell {
  id: string
  label: string
  value: string
}

export interface ChickenbroContextPanelProps {
  cells: readonly ChickenbroContextCell[]
  evidenceLabel: string
  onOpenWorkbench: () => void
}

function CaptainAvatar() {
  return (
    <View className={styles['captainAvatar'] ?? ''} data-slot-id="asset_slot.chickenbro-captain-avatar">
      <ProductionAssetGlyph
        assetId="mascot-shell-family.captain"
        dataRole="chickenbro-captain-glyph"
        fallbackAssetId="utility-glyph-family.assistant"
        fallbackSlotId="asset_slot.utility-glyph-family"
        slotId="asset_slot.chickenbro-captain-avatar"
      />
    </View>
  )
}

function UserAvatar() {
  return (
    <View className={styles['userAvatar'] ?? ''} data-slot-id="asset_slot.chickenbro-user-avatar">
      <SystemGlyph assetId="utility-glyph-family.user" dataRole="chickenbro-user-glyph" slotId="asset_slot.chickenbro-user-avatar" />
    </View>
  )
}

export function ChickenbroContextPanel({ cells, evidenceLabel, onOpenWorkbench }: ChickenbroContextPanelProps) {
  return (
    <View className={`${styles['contextPanel'] ?? ''} ${styleSelectorClass('chickenbroContextPanel')}`} data-owner="chickenbro-context-panel" data-region="workbench_context_panel">
      <View className={styles['contextHeading'] ?? ''}>
        <SystemGlyph assetId="utility-glyph-family.briefcase" slotId="asset_slot.chickenbro-context-family" />
        <Text>当前工作台</Text>
      </View>
      <View className={styles['contextCells'] ?? ''}>
        {cells.map((cell) => (
          <View key={cell.id} data-context-id={cell.id}>
            <Text>{cell.label}</Text>
            <View>
              <Text>{cell.value}</Text>
              <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.chickenbro-selector-affordances" />
            </View>
          </View>
        ))}
      </View>
      <View className={styles['contextFooter'] ?? ''}>
        <View>
          <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.chickenbro-context-family" />
          <Text>后端证据状态：{evidenceLabel}</Text>
        </View>
        <ControlButton data-action-id="open-workbench" onClick={onOpenWorkbench}>
          <Text>查看工作台</Text>
          <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.chickenbro-selector-affordances" />
        </ControlButton>
      </View>
    </View>
  )
}

export interface ChickenbroIntroMessageProps { content: string }

export function ChickenbroIntroMessage({ content }: ChickenbroIntroMessageProps) {
  return (
    <View className={`${styles['assistantMessage'] ?? ''} ${styleSelectorClass('chickenbroIntroMessage')}`} data-owner="chickenbro-intro-message" data-region="assistant_intro_message">
      <CaptainAvatar />
      <View className={styles['assistantBubble'] ?? ''}><Text>{content}</Text></View>
    </View>
  )
}

export interface ChickenbroUserTurnSlotProps {
  message?: ChatMessage | undefined
  region: 'user_question_primary' | 'user_question_followup'
}

export function ChickenbroUserTurnSlot({ message, region }: ChickenbroUserTurnSlotProps) {
  return (
    <View className={`${styles['userTurn'] ?? ''} ${styleSelectorClass(region === 'user_question_primary' ? 'chickenbroPrimaryUserTurn' : 'chickenbroFollowupUserTurn')}`} data-empty={message ? 'false' : 'true'} data-owner="chickenbro-user-turn-slot" data-region={region}>
      <View className={styles['userBubble'] ?? ''}>
        <Text>{message?.content || '等待你的真实问题'}</Text>
      </View>
      <UserAvatar />
    </View>
  )
}

export interface ChickenbroEvidenceRowItem {
  id: string
  title: string
  detail: string
  state: 'ready' | 'blocked'
}

export interface ChickenbroEvidenceAnswerProps {
  message?: ChatMessage | undefined
  sourceLabel: string
  confidenceLabel: string
  evidenceRows: readonly ChickenbroEvidenceRowItem[]
  evidenceCount: number
  onInspectEvidence: () => void
}

export function ChickenbroEvidenceAnswer({
  message,
  sourceLabel,
  confidenceLabel,
  evidenceRows,
  evidenceCount,
  onInspectEvidence,
}: ChickenbroEvidenceAnswerProps) {
  return (
    <View className={`${styles['evidenceAnswer'] ?? ''} ${styleSelectorClass('chickenbroEvidenceAnswer')}`} data-empty={message ? 'false' : 'true'} data-owner="chickenbro-evidence-answer" data-region="assistant_evidence_answer">
      <CaptainAvatar />
      <View className={styles['answerBubble'] ?? ''}>
        <Text className={styles['answerCopy'] ?? ''} data-role="chickenbro-answer-copy">{message?.content || '等待后端返回真实回答；当前不会展示目标图中的示例结论。'}</Text>
        <View className={styles['answerBasis'] ?? ''} data-role="chickenbro-answer-basis">
          <View className={styles['answerBasisHeader'] ?? ''}>
            <View>
              <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.chickenbro-answer-basis" />
              <View><Text>回答依据</Text><Text data-role="chickenbro-answer-source">{sourceLabel}</Text></View>
            </View>
            <Text data-role="chickenbro-confidence">{confidenceLabel}</Text>
          </View>
          <View className={styles['evidenceRows'] ?? ''}>
            {evidenceRows.map((row, index) => (
              <View key={row.id} data-evidence-id={row.id} data-role="chickenbro-evidence-row" data-state={row.state}>
                <SystemGlyph
                  assetId={index === 0 ? 'utility-glyph-family.document' : 'utility-glyph-family.source-link'}
                  dataRole="chickenbro-evidence-glyph"
                  slotId="asset_slot.chickenbro-evidence-rows"
                />
                <View>
                  <Text data-role="chickenbro-evidence-title">{row.title}</Text>
                  <Text data-role="chickenbro-evidence-detail">{row.detail}</Text>
                </View>
              </View>
            ))}
          </View>
          <ControlButton
            data-action-id="inspect-evidence"
            data-disabled={evidenceCount === 0 ? 'true' : 'false'}
            disabled={evidenceCount === 0}
            onClick={onInspectEvidence}
          >
            <Text>{evidenceCount ? `查看返回证据 (${evidenceCount})` : '没有返回证据'}</Text>
            <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.chickenbro-selector-affordances" />
          </ControlButton>
        </View>
      </View>
    </View>
  )
}

export interface ChickenbroBoundaryItem {
  id: string
  label: string
  state: 'ready' | 'unavailable'
}

export interface ChickenbroEvidenceBoundaryProps {
  missingInputs: readonly ChickenbroBoundaryItem[]
  limitations: readonly ChickenbroBoundaryItem[]
  helper: string
}

export function ChickenbroEvidenceBoundary({ missingInputs, limitations, helper }: ChickenbroEvidenceBoundaryProps) {
  const columns = [
    { id: 'missing', title: '缺少的输入', glyph: 'utility-glyph-family.warning', items: missingInputs },
    { id: 'limitations', title: '当前限制', glyph: 'utility-glyph-family.shield', items: limitations },
  ] as const
  return (
    <View className={`${styles['boundary'] ?? ''} ${styleSelectorClass('chickenbroEvidenceBoundary')}`} data-owner="chickenbro-evidence-boundary" data-region="evidence_boundary_panel">
      {columns.map((column) => (
        <View key={column.id} data-boundary-column={column.id}>
          <View className={styles['boundaryHeading'] ?? ''}>
            <SystemGlyph assetId={column.glyph} slotId="asset_slot.chickenbro-boundary-family" />
            <Text>{column.title}</Text>
          </View>
          <View className={styles['boundaryChips'] ?? ''}>
            {column.items.map((item) => <Text key={item.id} data-state={item.state}>{item.label}</Text>)}
          </View>
          <Text className={styles['boundaryHelper'] ?? ''}>{column.id === 'missing' ? helper : '只展示后端返回的限制'}</Text>
        </View>
      ))}
    </View>
  )
}

export interface ChickenbroAssistantTurnSlotProps { message?: ChatMessage | undefined }

export function ChickenbroAssistantTurnSlot({ message }: ChickenbroAssistantTurnSlotProps) {
  return (
    <View className={`${styles['assistantMessage'] ?? ''} ${styleSelectorClass('chickenbroFollowupAnswer')}`} data-empty={message ? 'false' : 'true'} data-owner="chickenbro-assistant-turn-slot" data-region="assistant_insufficient_evidence_message">
      <CaptainAvatar />
      <View className={styles['assistantBubble'] ?? ''}><Text>{message?.content || '等待下一条后端回答'}</Text></View>
    </View>
  )
}

export interface ChickenbroAnswerStatePanelProps {
  state: 'idle' | 'loading' | 'ready' | 'error'
  title: string
  detail: string
  canRetry: boolean
  onRetry: () => void
}

export function ChickenbroAnswerStatePanel({ state, title, detail, canRetry, onRetry }: ChickenbroAnswerStatePanelProps) {
  const retryDisabled = !canRetry || state === 'loading'
  return (
    <View className={`${styles['answerState'] ?? ''} ${styleSelectorClass('chickenbroAnswerState')}`} data-owner="chickenbro-answer-state-panel" data-region="answer_failure_panel" data-state={state}>
      <View className={styles['answerStateGlyph'] ?? ''} data-role="chickenbro-state-badge">
        <SystemGlyph assetId={state === 'error' ? 'utility-glyph-family.warning' : state === 'loading' ? 'utility-glyph-family.runtime' : 'utility-glyph-family.shield'} slotId="asset_slot.chickenbro-answer-state" />
      </View>
      <View><Text>{title}</Text><Text data-role="chickenbro-state-detail">{detail}</Text></View>
      <ControlButton data-action-id="retry" data-disabled={retryDisabled ? 'true' : 'false'} disabled={retryDisabled} onClick={onRetry}>
        <SystemGlyph assetId="utility-glyph-family.reset" slotId="asset_slot.chickenbro-answer-state" />
        <Text>重试</Text>
      </ControlButton>
    </View>
  )
}

export interface ChickenbroTopicLibraryProps {
  prompts: readonly string[]
  onSelect: (index: number) => void
}

export function ChickenbroTopicLibrary({ prompts, onSelect }: ChickenbroTopicLibraryProps) {
  return (
    <Picker className={styles['topicPicker'] ?? ''} mode="selector" range={[...prompts]} value={0} onChange={(event) => onSelect(Number(event.detail.value))}>
      <View className={`${styles['topicLibrary'] ?? ''} ${styleSelectorClass('chickenbroTopicLibrary')}`} data-owner="chickenbro-topic-library" data-region="topic_library_entry">
        <SystemGlyph assetId="utility-glyph-family.topic" slotId="asset_slot.chickenbro-topic-library" />
        <View><Text>常见问题</Text><Text data-role="chickenbro-topic-helper">选择安全问题填入输入框，不代表已有结论</Text></View>
        <SystemGlyph assetId="utility-glyph-family.chevron-right" slotId="asset_slot.chickenbro-selector-affordances" />
      </View>
    </Picker>
  )
}

export interface ChickenbroComposerProps {
  draft: string
  state: 'idle' | 'loading' | 'ready' | 'error'
  onDraftChange: (value: string) => void
  onNewTopic: () => void
  onSend: () => void
}

export function ChickenbroComposer({ draft, state, onDraftChange, onNewTopic, onSend }: ChickenbroComposerProps) {
  const loading = state === 'loading'
  const sendDisabled = loading || !draft.trim()
  return (
    <View className={`${styles['composer'] ?? ''} ${styleSelectorClass('chickenbroComposer')}`} data-owner="chickenbro-composer" data-region="composer_dock" data-state={state}>
      <ControlButton className={styleSelectorClass('chickenbroNewTopic')} data-action-id="new-topic" data-disabled={loading ? 'true' : 'false'} disabled={loading} onClick={onNewTopic}>
        <SystemGlyph assetId="utility-glyph-family.plus" dataRole="chickenbro-new-topic-glyph" slotId="asset_slot.chickenbro-composer-actions" />
        <Text>新话题</Text>
      </ControlButton>
      <View className={styles['composerField'] ?? ''} data-role="chickenbro-composer-field">
        <Textarea
          className={styleSelectorClass('chickenbroPrompt')}
          data-action-id="prompt"
          disabled={loading}
          maxlength={2000}
          nativeProps={{ style: { resize: 'none' } }}
          placeholder="问炸鸡队长..."
          value={draft}
          onInput={(event) => onDraftChange(event.detail.value)}
        />
        <Text>只解释后端证据，缺资料时先给下一步</Text>
      </View>
      <ControlButton
        className={styles['sendAction'] ?? ''}
        data-action-id="send"
        data-disabled={sendDisabled ? 'true' : 'false'}
        disabled={sendDisabled}
        onClick={onSend}
      >
        <SystemGlyph assetId="utility-glyph-family.send" dataRole="chickenbro-send-glyph" slotId="asset_slot.chickenbro-composer-actions" />
        <Text>{loading ? '发送中' : '发送'}</Text>
      </ControlButton>
    </View>
  )
}
