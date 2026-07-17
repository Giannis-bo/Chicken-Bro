import { ScrollView, Text, Textarea, View } from '@tarojs/components'

import type { ChatMessage } from '@wow-mini/domain'

import { ProductionAssetGlyph } from './ProductionAssetGlyph'
import { styleSelectorClass } from './selector-markers'
import { SystemGlyph } from './SystemGlyph'

import styles from './SimulatorHomeComponents.module.scss'

export type SimulatorInputState = 'ready' | 'loading' | 'error'

export interface SimulatorCaptainActionProps {
  disabled?: boolean | undefined
  onReset: () => void
}

export function SimulatorCaptainAction({ disabled = false, onReset }: SimulatorCaptainActionProps) {
  return (
    <View
      className={`${styles['captainAction'] ?? ''} ${styles['interactive'] ?? ''} ${styleSelectorClass('simulatorCaptainAction')}`}
      data-action-id="new-topic"
      data-disabled={disabled ? 'true' : 'false'}
      data-material-owner="css"
      role="button"
      onClick={() => { if (!disabled) onReset() }}
    >
      <View className={styles['captainMedallion'] ?? ''}>
        <ProductionAssetGlyph
          assetId="mascot-shell-family.captain"
          fallbackAssetId="utility-glyph-family.assistant"
          fallbackSlotId="asset_slot.utility-glyph-family"
          slotId="asset_slot.mascot-shell-family"
        />
        <SystemGlyph
          assetId="utility-glyph-family.reset"
          className={styles['captainResetGlyph'] ?? ''}
          slotId="asset_slot.utility-glyph-family"
        />
      </View>
      <View className={styles['captainActionCopy'] ?? ''}>
        <Text>新话题</Text>
      </View>
    </View>
  )
}

export interface SimulatorGuidancePanelProps {
  answerSourceLabel: string
  confidenceLabel: string
  evidenceCount: number
  evidenceStateLabel: string
  missingInputs: readonly string[]
  limitations: readonly string[]
  suggestions: readonly string[]
  onManageEvidence: () => void
  onSuggestion: (suggestion: string) => void
}

function boundaryDetail(
  missingInputs: readonly string[],
  limitations: readonly string[],
): string {
  if (missingInputs.length) return `待补输入：${missingInputs.join('、')}`
  if (limitations.length) return `当前限制：${limitations.join('、')}`
  return '证据越完整，回答边界越清楚。'
}

export function SimulatorGuidancePanel({
  answerSourceLabel,
  confidenceLabel,
  evidenceCount,
  evidenceStateLabel,
  missingInputs,
  limitations,
  suggestions,
  onManageEvidence,
  onSuggestion,
}: SimulatorGuidancePanelProps) {
  const visibleSuggestions = suggestions.slice(0, 3)

  return (
    <View
      className={`${styles['guidance'] ?? ''} ${styleSelectorClass('simulatorGuidance')}`}
      data-evidence-count={evidenceCount}
      data-owner="simulator-guidance-panel"
      data-region="analysis_guidance_panel"
    >
      <View className={styles['guidanceHeader'] ?? ''} data-layout-slot="context-heading" data-role="simulator-guidance-header">
        <View className={styles['guidanceIdentity'] ?? ''}>
          <View className={styles['guidanceEmblem'] ?? ''}>
            <SystemGlyph
              assetId="utility-glyph-family.assistant"
              slotId="asset_slot.simulator-context-emblem"
            />
          </View>
          <View className={styles['guidanceTitleStack'] ?? ''}>
            <Text className={styles['guidanceKicker'] ?? ''}>问炸鸡队长</Text>
            <Text className={styles['guidanceTitle'] ?? ''}>当前分析上下文</Text>
          </View>
        </View>
        <View className={styles['confidenceChip'] ?? ''} data-role="simulator-confidence">
          <Text>{confidenceLabel}</Text>
        </View>
      </View>

      <View className={styles['contextPanel'] ?? ''} data-layout-slot="context-state" data-role="simulator-context-well">
        <View className={styles['contextMain'] ?? ''}>
          <View className={styles['contextSource'] ?? ''}>
            <SystemGlyph
              assetId="utility-glyph-family.source-link"
              slotId="asset_slot.utility-glyph-family"
            />
            <Text data-role="simulator-answer-source">{answerSourceLabel}</Text>
          </View>
          <Text className={styles['contextState'] ?? ''} data-role="simulator-evidence-state">
            {evidenceStateLabel}
          </Text>
          <Text className={styles['contextBoundary'] ?? ''}>
            {boundaryDetail(missingInputs, limitations)}
          </Text>
        </View>
        <View className={styles['evidenceRail'] ?? ''} data-state={evidenceCount > 0 ? 'ready' : 'blocked'}>
          <View />
        </View>
        <View className={styles['contextFooter'] ?? ''}>
          <Text>证据越完整，回答边界越清楚。</Text>
          <View
            className={`${styles['contextManage'] ?? ''} ${styles['interactive'] ?? ''}`}
            data-action-id="manage-context-evidence"
            role="button"
            onClick={onManageEvidence}
          >
            管理证据
          </View>
        </View>
      </View>

      <View className={styles['suggestionHeader'] ?? ''} data-layout-slot="suggestion-heading">
        <Text>建议你这样问</Text>
        <Text>只填入问题，不代表已有结论</Text>
      </View>
      <View className={styles['suggestionList'] ?? ''} data-layout-slot="suggestion-list">
        {visibleSuggestions.map((suggestion, index) => (
          <View
            key={suggestion}
            className={`${styles['suggestion'] ?? ''} ${styles['interactive'] ?? ''}`}
            data-suggestion-id={`suggestion-${index + 1}`}
            role="button"
            onClick={() => onSuggestion(suggestion)}
          >
            <SystemGlyph
              assetId={index === 0
                ? 'utility-glyph-family.warning'
                : index === 1
                  ? 'utility-glyph-family.document'
                  : 'utility-glyph-family.source-link'}
              dataRole="simulator-suggestion-glyph"
              slotId="asset_slot.simulator-suggestion-family"
            />
            <Text>{suggestion}</Text>
            <SystemGlyph
              assetId="utility-glyph-family.chevron-right"
              slotId="asset_slot.simulator-suggestion-family"
            />
          </View>
        ))}
      </View>
    </View>
  )
}

export interface SimulatorTranscriptProps {
  messages: readonly ChatMessage[]
  inputState: SimulatorInputState
  onRetry: () => void
}

function MessageAvatar({ role }: { role: ChatMessage['role'] }) {
  return role === 'assistant' ? (
    <View className={styles['assistantAvatar'] ?? ''} data-role="assistant-avatar">
      <ProductionAssetGlyph
        assetId="mascot-shell-family.captain"
        fallbackAssetId="utility-glyph-family.assistant"
        fallbackSlotId="asset_slot.utility-glyph-family"
        slotId="asset_slot.simulator-chat-avatars"
      />
    </View>
  ) : (
    <View className={styles['userAvatar'] ?? ''} data-role="neutral-user-avatar">
      <SystemGlyph
        assetId="utility-glyph-family.user"
        dataRole="simulator-user-glyph"
        slotId="asset_slot.simulator-chat-avatars"
      />
    </View>
  )
}

export function SimulatorTranscript({ messages, inputState, onRetry }: SimulatorTranscriptProps) {
  const visibleMessages = messages.slice(-8)

  return (
    <View
      className={`${styles['transcript'] ?? ''} ${styleSelectorClass('simulatorTranscript')}`}
      data-message-count={messages.length}
      data-owner="simulator-transcript"
      data-region="chat_transcript"
    >
      <ScrollView className={styles['transcriptScroll'] ?? ''} scrollY scrollWithAnimation>
        <View className={styles['messageList'] ?? ''}>
          {visibleMessages.map((message, index) => (
            <View
              key={message.messageId ?? `${message.role}-${index}`}
              className={`${styles['messageRow'] ?? ''} ${message.role === 'user' ? styles['messageRowUser'] ?? '' : styles['messageRowAssistant'] ?? ''}`}
              data-message-role={message.role}
            >
              <MessageAvatar role={message.role} />
              <View className={styles['messageContent'] ?? ''}>
                <View className={styles['messageBubble'] ?? ''} data-role="simulator-message-bubble">
                  <Text>{message.content}</Text>
                </View>
                {message.status ? <Text className={styles['messageStatus'] ?? ''}>{message.status}</Text> : null}
              </View>
            </View>
          ))}
          {inputState === 'loading' ? (
            <View className={`${styles['messageRow'] ?? ''} ${styles['messageRowAssistant'] ?? ''}`} data-message-state="loading">
              <MessageAvatar role="assistant" />
              <View className={styles['messageContent'] ?? ''}>
                <View className={styles['messageBubble'] ?? ''}><Text>正在等待后端回答...</Text></View>
                <Text className={styles['messageStatus'] ?? ''}>不会生成本地假结论</Text>
              </View>
            </View>
          ) : null}
          {inputState === 'error' ? (
            <View className={styles['transportError'] ?? ''} data-message-state="error">
              <SystemGlyph assetId="utility-glyph-family.warning" slotId="asset_slot.utility-glyph-family" />
              <View>
                <Text>服务未返回可信回答</Text>
                <Text>已保留上次问题，可直接重试。</Text>
              </View>
              <View className={styles['interactive'] ?? ''} data-action-id="retry" role="button" onClick={onRetry}>重试</View>
            </View>
          ) : null}
          {inputState === 'ready' && visibleMessages.length <= 1 ? (
            <View className={styles['transcriptEmpty'] ?? ''} data-role="simulator-transcript-empty">
              <View className={styles['transcriptEmptyEmblem'] ?? ''}>
                <SystemGlyph assetId="utility-glyph-family.topic" slotId="asset_slot.utility-glyph-family" />
              </View>
              <View className={styles['transcriptEmptyCopy'] ?? ''}>
                <Text>等待你的问题</Text>
                <Text>发送问题后，这里会按真实后端返回形成连续对话。</Text>
              </View>
              <View className={styles['transcriptEmptyBoundary'] ?? ''}>
                <Text>不生成历史对话</Text>
                <Text>不伪造时间戳</Text>
                <Text>不填充虚构证据</Text>
              </View>
            </View>
          ) : null}
        </View>
      </ScrollView>
    </View>
  )
}

export interface SimulatorEvidenceCard {
  id: string
  eyebrow: string
  title: string
  state: 'ready' | 'blocked' | 'unavailable'
}

export interface SimulatorEvidenceShelfProps {
  cards: readonly SimulatorEvidenceCard[]
  evidenceCount: number
  onManageEvidence: () => void
}

export function SimulatorEvidenceShelf({ cards, evidenceCount, onManageEvidence }: SimulatorEvidenceShelfProps) {
  const visibleCards = cards.slice(0, 3)

  return (
    <View
      className={`${styles['evidenceShelf'] ?? ''} ${styleSelectorClass('simulatorEvidenceShelf')}`}
      data-owner="simulator-evidence-shelf"
    >
      <View className={styles['evidenceHeader'] ?? ''}>
        <View className={styles['evidenceHeaderIdentity'] ?? ''}>
          <View className={styles['evidenceModeEmblem'] ?? ''} data-role="simulator-evidence-mode-emblem">
            <SystemGlyph assetId="utility-glyph-family.records" slotId="asset_slot.simulator-evidence-shelf" />
          </View>
          <View>
            <Text>只解释证据</Text>
            <Text>{evidenceCount > 0 ? `当前可引用 ${evidenceCount} 条` : '尚无可引用证据'}</Text>
          </View>
        </View>
        <View className={styles['interactive'] ?? ''} data-action-id="manage-evidence" role="button" onClick={onManageEvidence}>管理证据</View>
      </View>
      <View className={styles['evidenceCards'] ?? ''}>
        {visibleCards.map((card) => (
          <View key={card.id} className={styles['evidenceCard'] ?? ''} data-evidence-id={card.id} data-state={card.state}>
            <SystemGlyph
              assetId={card.state === 'ready'
                ? 'utility-glyph-family.source-link'
                : card.state === 'unavailable'
                  ? 'utility-glyph-family.topic'
                  : 'utility-glyph-family.warning'}
              slotId="asset_slot.simulator-evidence-shelf"
            />
            <View>
              <Text>{card.eyebrow}</Text>
              <Text>{card.title}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  )
}

export interface SimulatorComposerProps {
  draft: string
  inputState: SimulatorInputState
  onDraftChange: (value: string) => void
  onRetry: () => void
  onSend: () => void
}

export function SimulatorComposer({
  draft,
  inputState,
  onDraftChange,
  onRetry,
  onSend,
}: SimulatorComposerProps) {
  const loading = inputState === 'loading'
  const canSubmit = Boolean(draft.trim()) && !loading
  const retrying = inputState === 'error'

  return (
    <View
      className={`${styles['composer'] ?? ''} ${styleSelectorClass('simulatorComposer')}`}
      data-input-state={inputState}
      data-owner="simulator-composer"
      data-region="message_composer"
    >
      <Textarea
        className={`${styles['composerInput'] ?? ''} ${styleSelectorClass('simulatorPrompt')}`}
        data-role="simulator-prompt"
        disabled={loading}
        maxlength={2000}
        placeholder="继续提问，或补充可验证的资料文本..."
        value={draft}
        onInput={(event) => onDraftChange(event.detail.value)}
      />
      <View className={styles['composerActions'] ?? ''}>
        <View className={styles['interactive'] ?? ''} aria-label="上传证据暂未开放" data-action-id="upload-evidence" data-disabled="true" role="button">
          <SystemGlyph assetId="utility-glyph-family.document" slotId="asset_slot.simulator-composer-family" />
          <Text>上传证据</Text>
        </View>
        <View className={styles['interactive'] ?? ''} aria-label="粘贴链接暂未开放" data-action-id="paste-link" data-disabled="true" role="button">
          <SystemGlyph assetId="utility-glyph-family.source-link" slotId="asset_slot.simulator-composer-family" />
          <Text>粘贴链接</Text>
        </View>
        <View
          className={`${styles['sendAction'] ?? ''} ${styles['interactive'] ?? ''}`}
          data-action-id="send"
          data-action-mode={retrying ? 'retry' : 'send'}
          data-disabled={retrying ? (loading ? 'true' : 'false') : (!canSubmit ? 'true' : 'false')}
          role="button"
          onClick={() => {
            if (retrying ? !loading : canSubmit) (retrying ? onRetry : onSend)()
          }}
        >
          <SystemGlyph
            assetId="utility-glyph-family.send"
            dataRole="simulator-send-glyph"
            slotId="asset_slot.simulator-composer-family"
          />
          <Text>{loading ? '发送中' : retrying ? '重试' : '发送'}</Text>
        </View>
      </View>
    </View>
  )
}
