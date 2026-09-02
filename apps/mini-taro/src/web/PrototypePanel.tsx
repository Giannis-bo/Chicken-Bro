import { Input, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'

import type {
  PrototypeChatStreamEvent,
  PrototypeConversationResponse,
  PrototypeSimulationResponse,
  PrototypeSnapshotResponse,
} from '@wow-mini/domain'
import type { ApiResult, PrototypeWebClient } from '@wow-mini/api-client'
import { wowApi } from '@wow-mini/api-client'

import { ActionButton } from '@wow-mini/design-system/components/ActionButton'

import stylesModule from './PrototypePanel.module.scss'

type PrototypeStyles = Partial<{
  assistantMessage: string
  backdrop: string
  blockedState: string
  blockedTitle: string
  blocker: string
  blockerList: string
  brandMark: string
  brandMeta: string
  brandName: string
  brandRow: string
  card: string
  cardDescription: string
  cardHeader: string
  cardKicker: string
  cardState: string
  cardTitle: string
  composer: string
  content: string
  empty: string
  error: string
  eyebrow: string
  footer: string
  ghostAction: string
  grid: string
  hero: string
  jobPanel: string
  jobStatus: string
  lede: string
  message: string
  messageList: string
  messageRole: string
  messageText: string
  muted: string
  notice: string
  noticeDot: string
  page: string
  primaryAction: string
  provenance: string
  readinessLabel: string
  readinessPanel: string
  resultNumber: string
  resultPanel: string
  secondaryAction: string
  sessionBadge: string
  shell: string
  signal: string
  signalRow: string
  sourceInput: string
  sourceRow: string
  textarea: string
  title: string
  topActions: string
  topbar: string
  userMessage: string
}>

const styles = stylesModule as unknown as PrototypeStyles

interface PrototypePanelProps {
  client?: PrototypeWebClient
  onOpenFormalLogin: () => void
}

type PrototypePhase = 'starting' | 'ready' | 'blocked'

const errorCopy: Record<string, string> = {
  PROTOTYPE_DISABLED: 'Web 原型暂未开放，请稍后再试。',
  PROTOTYPE_SESSION_REQUIRED: '演示会话已失效，请重置后重新开始。',
  CODEX_UNAVAILABLE: '原生 Codex 当前不可用；本次没有切换到其他模型。',
  CODEX_TIMEOUT: '原生 Codex 响应超时，请稍后重试。',
  CODEX_OUTPUT_INVALID: 'Codex 返回内容不完整，本次没有写入助手消息。',
  INVALID_LINK: '链接必须是 Raider.IO 或 Warcraft Logs 的 HTTPS 角色/报告链接。',
  ACCESS_RESTRICTED: '来源访问受限，暂时无法读取这份角色快照。',
  CHARACTER_NOT_FOUND: '来源中没有找到可识别的角色或报告。',
  SNAPSHOT_UNAVAILABLE: '来源暂时不可用，请稍后重新解析。',
  INCOMPLETE_FOR_SIMC: '角色快照字段不足，暂时不能进入 SimC。',
  SNAPSHOT_NOT_READY: '这份快照还没有达到 SimC 提交条件。',
  SIMC_UNAVAILABLE: 'SimC runtime 当前不可用，任务不会伪装成成功。',
  SIMC_METRIC_MISSING: 'SimC 没有返回有效主指标，任务已明确失败。',
  SIMC_EXECUTION_FAILED: 'SimC 执行失败，请稍后重试。',
}

const blockerCopy: Record<string, string> = {
  CHARACTER_LEVEL_MISSING: '等级字段缺失；原型按满级策略处理，请重新解析来源。',
  GEAR_OFF_HAND_MISSING: '来源未返回副手装备；如果这是双手武器，系统会按无副手处理。',
  SOURCE_PROVENANCE_MISSING: '来源版本或抓取时间缺失，无法确认这份快照的出处。',
  SOURCE_HASH_MISSING: '来源原始数据校验值缺失，无法冻结这份快照。',
  TALENTS_MISSING: '天赋数据缺失，不能安全生成 SimC profile。',
  RUNTIME_UNAVAILABLE: '当前 SimC runtime 不支持这个职业/专精。',
  COMPILER_UNAVAILABLE: '当前 SimC profile 编译器不可用。',
}

function resultProblem(result: ApiResult<unknown>, fallback: string): string {
  return errorCopy[result.problemCode ?? ''] ?? result.error ?? fallback
}

function newId(prefix: string): string {
  const random = Math.random().toString(36).slice(2)
  return `${prefix}-${Date.now().toString(36)}-${random}`
}

function readinessLabel(snapshot: PrototypeSnapshotResponse | null): string {
  if (!snapshot) return '待输入角色链接'
  if (snapshot.readiness === 'READY_FOR_SIMC') return '已就绪，可提交 SimC'
  return errorCopy[snapshot.readiness] ?? snapshot.readiness
}

function blockerLabel(blocker: string): string {
  return blockerCopy[blocker] ?? blocker
}

function snapshotCharacter(snapshot: PrototypeSnapshotResponse | null): string {
  const character = snapshot?.snapshot?.['character']
  if (!character || typeof character !== 'object') return ''
  const record = character as Record<string, unknown>
  const name = typeof record['name'] === 'string' ? record['name'] : ''
  const spec = typeof record['specKey'] === 'string' ? record['specKey'] : ''
  const realm = typeof record['realm'] === 'string' ? record['realm'] : ''
  const level = typeof record['level'] === 'number' ? record['level'] : null
  const levelLabel = record['levelSource'] === 'prototype_max_level' && level ? `按满级 ${level} 处理` : ''
  return [name, spec, realm, levelLabel].filter(Boolean).join(' · ')
}

function appendChatEvent(
  current: PrototypeChatStreamEvent | undefined,
  next: PrototypeChatStreamEvent,
): PrototypeChatStreamEvent {
  if (next.type !== 'delta' || current?.type !== 'delta') return next
  return { ...next, text: current.text + next.text }
}

export default function PrototypePanel({ client = wowApi.prototype, onOpenFormalLogin }: PrototypePanelProps) {
  const [phase, setPhase] = useState<PrototypePhase>('starting')
  const [error, setError] = useState('')
  const [conversation, setConversation] = useState<PrototypeConversationResponse | null>(null)
  const [messages, setMessages] = useState<PrototypeConversationResponse['messages']>([])
  const [draft, setDraft] = useState('')
  const [streamText, setStreamText] = useState('')
  const [chatState, setChatState] = useState<'idle' | 'streaming' | 'failed'>('idle')
  const [sourceUrl, setSourceUrl] = useState('')
  const [snapshot, setSnapshot] = useState<PrototypeSnapshotResponse | null>(null)
  const [snapshotError, setSnapshotError] = useState('')
  const [simJob, setSimJob] = useState<PrototypeSimulationResponse | null>(null)
  const streamTaskRef = useRef<{ abort(): void } | null>(null)

  const initialize = async () => {
    setPhase('starting')
    setError('')
    let sessionToken = client.getSessionToken()
    if (!sessionToken) {
      const created = await client.createSession()
      if (created.fromFallback || !created.payload.sessionToken) {
        setPhase('blocked')
        setError(resultProblem(created, '演示会话创建失败，请稍后重试。'))
        return
      }
      sessionToken = created.payload.sessionToken
    }
    if (!sessionToken) {
      setPhase('blocked')
      setError('当前浏览器无法保存演示会话，请使用正常浏览模式。')
      return
    }
    let createdConversation = await client.createConversation()
    if (createdConversation.fromFallback && createdConversation.httpStatus === 401) {
      await client.resetSession()
      const renewed = await client.createSession()
      if (renewed.fromFallback || !renewed.payload.sessionToken) {
        setPhase('blocked')
        setError(resultProblem(renewed, '演示会话已失效，请重试。'))
        return
      }
      createdConversation = await client.createConversation()
    }
    if (createdConversation.fromFallback || !createdConversation.payload.conversationId) {
      setPhase('blocked')
      setError(resultProblem(createdConversation, '对话工作台暂时不可用。'))
      return
    }
    setConversation(createdConversation.payload)
    setMessages(createdConversation.payload.messages)
    setPhase('ready')
  }

  useEffect(() => {
    void initialize()
    return () => streamTaskRef.current?.abort()
  }, [client])

  useEffect(() => {
    if (!simJob || !['queued', 'running'].includes(simJob.status)) return undefined
    let active = true
    const poll = async () => {
      const result = await client.getSimulation(simJob.jobId)
      if (active && !result.fromFallback) setSimJob(result.payload)
    }
    const timer = setInterval(() => { void poll() }, 2000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [client, simJob?.jobId, simJob?.status])

  const sendMessage = () => {
    if (!conversation?.conversationId || !draft.trim() || chatState === 'streaming') return
    const content = draft.trim()
    const clientMessageId = newId('message')
    const idempotencyKey = newId('chat')
    setDraft('')
    setStreamText('')
    setChatState('streaming')
    setError('')
    const userMessage = {
      messageId: clientMessageId,
      role: 'user' as const,
      content,
      createdAt: new Date().toISOString(),
    }
    setMessages((current) => [...current, userMessage])
    let lastEvent: PrototypeChatStreamEvent | undefined
    streamTaskRef.current = client.streamMessage(
      conversation.conversationId,
      content,
      clientMessageId,
      idempotencyKey,
      {
        onEvent: (event) => {
          lastEvent = appendChatEvent(lastEvent, event)
          if (event.type === 'delta') setStreamText((current) => current + event.text)
          if (event.type === 'completed') {
            setMessages((current) => [...current, {
              messageId: newId('assistant'),
              role: 'assistant' as const,
              content: event.text,
              createdAt: new Date().toISOString(),
            }])
            setStreamText('')
            setChatState('idle')
          }
          if (event.type === 'failed') {
            setChatState('failed')
            setError(errorCopy[event.errorCode] ?? `Codex 失败：${event.errorCode}`)
          }
        },
        onFailure: (message) => {
          setChatState('failed')
          setError(errorCopy[message] ?? message)
        },
      },
    )
  }

  const resolveSource = async () => {
    if (!sourceUrl.trim()) return
    setSnapshotError('')
    setSnapshot(null)
    setSimJob(null)
    const result = await client.resolveSnapshot(sourceUrl.trim())
    if (result.fromFallback) {
      setSnapshotError(resultProblem(result, '来源解析失败，请稍后重试。'))
      return
    }
    setSnapshot(result.payload)
  }

  const submitSimulation = async () => {
    if (!snapshot || snapshot.readiness !== 'READY_FOR_SIMC') return
    setSnapshotError('')
    const result = await client.submitSimulation(
      snapshot.snapshotId,
      { fightStyle: 'Patchwerk', desiredTargets: 1, iterations: 300 },
      newId('simulation'),
    )
    if (result.fromFallback) {
      setSnapshotError(resultProblem(result, 'SimC 任务提交失败。'))
      return
    }
    setSimJob(result.payload)
  }

  const resetSession = async () => {
    streamTaskRef.current?.abort()
    await client.resetSession()
    setConversation(null)
    setMessages([])
    setSnapshot(null)
    setSimJob(null)
    await initialize()
  }

  const simResult = simJob?.result
  const simReady = snapshot?.readiness === 'READY_FOR_SIMC'

  return (
    <View className={styles.page ?? ''} data-prototype-phase={phase} data-prototype-auth-storage="sessionStorage-only">
      <View className={styles.backdrop ?? ''} />
      <View className={styles.shell ?? ''}>
        <View className={styles.topbar ?? ''}>
          <View className={styles.brandRow ?? ''}>
            <View className={styles.brandMark ?? ''}>CB</View>
            <View>
              <Text className={styles.brandName ?? ''}>CHICKENBRO</Text>
              <Text className={styles.brandMeta ?? ''}>WEB PROTOTYPE · CODEx + SIMC DESK</Text>
            </View>
          </View>
          <View className={styles.topActions ?? ''}>
            <Text className={styles.sessionBadge ?? ''}>{phase === 'ready' ? 'DEMO SESSION READY' : 'DEMO SESSION'}</Text>
            <ActionButton className={styles.ghostAction ?? ''} variant="secondaryMetal" onClick={() => void resetSession()}>
              重置演示会话
            </ActionButton>
            <ActionButton className={styles.ghostAction ?? ''} variant="secondaryMetal" onClick={onOpenFormalLogin}>
              正式微信登录
            </ActionButton>
          </View>
        </View>

        <View className={styles.notice ?? ''}>
          <View className={styles.noticeDot ?? ''} />
          <Text>这是独立 prototype owner：当前标签页只保存短期演示 token，不读取正式 Cookie、/api/v2/me 或小程序登录凭据。</Text>
        </View>

        {phase === 'blocked' ? (
          <View className={styles.blockedState ?? ''}>
            <Text className={styles.blockedTitle ?? ''}>演示工作台暂不可用</Text>
            <Text className={styles.muted ?? ''}>{error || '请重新初始化当前标签页。'}</Text>
            <ActionButton className={styles.primaryAction ?? ''} variant="primaryGold" onClick={() => void initialize()}>
              重新初始化
            </ActionButton>
          </View>
        ) : (
          <View className={styles.content ?? ''}>
            <View className={styles.hero ?? ''}>
              <Text className={styles.eyebrow ?? ''}>原生 Codex · 真实来源快照 · 语义 SimC 结果</Text>
              <Text className={styles.title ?? ''}>先把事实接上，再让队长给结论。</Text>
              <Text className={styles.lede ?? ''}>
                 这里是 Web 端的可逆体验原型。对话只走原生 Codex；角色模拟只接受 Raider.IO 或 Warcraft Logs 的真实快照，等级按原型满级策略处理，其他字段不完整仍会停在明确阻塞状态。
              </Text>
              <View className={styles.signalRow ?? ''}>
                <View className={styles.signal ?? ''} data-tone="ready" />
                <Text>owner isolation</Text>
                <View className={styles.signal ?? ''} data-tone="gold" />
                <Text>source provenance</Text>
                <View className={styles.signal ?? ''} data-tone="blue" />
                <Text>semantic result only</Text>
              </View>
            </View>

            <View className={styles.grid ?? ''}>
              <View className={styles.card ?? ''} data-card="chickenbro">
                <View className={styles.cardHeader ?? ''}>
                  <View>
                    <Text className={styles.cardKicker ?? ''}>01 · CHICKENBRO</Text>
                    <Text className={styles.cardTitle ?? ''}>和炸鸡队长聊两句</Text>
                  </View>
                  <Text className={styles.cardState ?? ''}>{chatState === 'streaming' ? 'CODEX STREAMING' : 'CODEX ONLY'}</Text>
                </View>
                <View className={styles.messageList ?? ''}>
                  {messages.length === 0 ? <Text className={styles.empty ?? ''}>输入一个问题，原生 Codex 会把回答逐段送回来。</Text> : null}
                  {messages.map((message) => (
                    <View key={message.messageId} className={`${styles.message ?? ''} ${message.role === 'user' ? styles.userMessage ?? '' : styles.assistantMessage ?? ''}`}>
                      <Text className={styles.messageRole ?? ''}>{message.role === 'user' ? '你' : '队长'}</Text>
                      <Text className={styles.messageText ?? ''}>{message.content}</Text>
                    </View>
                  ))}
                  {streamText ? (
                    <View className={`${styles.message ?? ''} ${styles.assistantMessage ?? ''}`} data-streaming="true">
                      <Text className={styles.messageRole ?? ''}>队长 · streaming</Text>
                      <Text className={styles.messageText ?? ''}>{streamText}</Text>
                    </View>
                  ) : null}
                </View>
                {error ? <Text className={styles.error ?? ''}>{error}</Text> : null}
                <View className={styles.composer ?? ''}>
                  <Textarea
                    className={styles.textarea ?? ''}
                    value={draft}
                    maxlength={4000}
                    placeholder="例如：这个角色的单体模拟应该先看什么？"
                    onInput={(event) => setDraft(event.detail.value)}
                  />
                  <ActionButton className={styles.primaryAction ?? ''} variant="primaryGold" onClick={sendMessage}>
                    {chatState === 'streaming' ? '正在回答…' : '发送给队长'}
                  </ActionButton>
                </View>
              </View>

              <View className={styles.card ?? ''} data-card="simc">
                <View className={styles.cardHeader ?? ''}>
                  <View>
                    <Text className={styles.cardKicker ?? ''}>02 · SIMC</Text>
                    <Text className={styles.cardTitle ?? ''}>接入真实角色快照</Text>
                  </View>
                  <Text className={styles.cardState ?? ''}>{snapshot?.provider?.toUpperCase() ?? 'WAITING SOURCE'}</Text>
                </View>
                <Text className={styles.cardDescription ?? ''}>
                  粘贴 Raider.IO 角色链接，或带 fight/source 的 Warcraft Logs 报告链接。角色等级按满级处理；后端会保存来源版本与 hash，不接受客户端 profile。
                </Text>
                <View className={styles.sourceRow ?? ''}>
                  <Input
                    className={styles.sourceInput ?? ''}
                    value={sourceUrl}
                    placeholder="https://raider.io/characters/..."
                    onInput={(event) => setSourceUrl(event.detail.value)}
                  />
                  <ActionButton className={styles.secondaryAction ?? ''} variant="secondaryMetal" onClick={() => void resolveSource()}>
                    解析来源
                  </ActionButton>
                </View>
                <View className={styles.readinessPanel ?? ''} data-readiness={snapshot?.readiness ?? 'idle'}>
                  <Text className={styles.readinessLabel ?? ''}>{readinessLabel(snapshot)}</Text>
                  {snapshotCharacter(snapshot) ? <Text className={styles.muted ?? ''}>{snapshotCharacter(snapshot)}</Text> : null}
                  {snapshot?.blockers?.length ? (
                    <View className={styles.blockerList ?? ''}>
                      {snapshot.blockers.map((blocker) => <Text key={blocker} className={styles.blocker ?? ''}>{blockerLabel(blocker)}</Text>)}
                    </View>
                  ) : null}
                  {snapshot ? (
                    <Text className={styles.provenance ?? ''}>
                      {snapshot.provider} · rev {snapshot.revision} · raw {snapshot.rawSha256.slice(0, 12)}…
                    </Text>
                  ) : null}
                </View>
                {snapshotError ? <Text className={styles.error ?? ''}>{snapshotError}</Text> : null}
                <ActionButton
                  className={styles.primaryAction ?? ''}
                  variant="primaryGold"
                  onClick={() => void submitSimulation()}
                  disabled={!simReady || simJob?.status === 'queued' || simJob?.status === 'running'}
                >
                  {simJob?.status === 'queued' || simJob?.status === 'running' ? 'SimC 任务进行中…' : '提交单体 Patchwerk SimC'}
                </ActionButton>
                {simJob ? (
                  <View className={styles.jobPanel ?? ''} data-job-status={simJob.status}>
                    <Text className={styles.jobStatus ?? ''}>任务：{simJob.status}</Text>
                    {simJob.errorCode ? <Text className={styles.error ?? ''}>{errorCopy[simJob.errorCode] ?? simJob.errorCode}</Text> : null}
                    {simResult ? (
                      <View className={styles.resultPanel ?? ''}>
                        <Text className={styles.resultNumber ?? ''}>{Math.round(simResult.metric.value).toLocaleString()}</Text>
                        <Text className={styles.muted ?? ''}>{simResult.metric.name.toUpperCase()} · runtime {simResult.runtimeRevision}</Text>
                      </View>
                    ) : null}
                  </View>
                ) : null}
              </View>
            </View>
          </View>
        )}
        <View className={styles.footer ?? ''}>
          <Text>Prototype bypass 可随时重置；正式二维码登录保留为独立入口。</Text>
          <Text>失败状态不会降级成普通模型、默认人物或伪造 DPS。</Text>
        </View>
      </View>
    </View>
  )
}
