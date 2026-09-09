import { useEffect, useRef, useState } from 'react'
import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'
import type { ChatImage } from '@wow-mini/domain'
import { chooseChatImages } from './image-picker'

export interface DraftImage { key: string; dataUrl: string; status: 'uploading' | 'ready' | 'failed'; image?: ChatImage }
let sequence = 0
export function useChatImages(authProvider: () => ClientAuthContext, enabledSession: boolean) {
  let sessionKey = ''
  try {
    const context = authProvider()
    sessionKey = context.kind === 'web' ? context.csrfToken : context.kind === 'mini' ? context.accessToken : ''
  } catch { /* No active session. */ }
  const [enabled, setEnabled] = useState(false)
  const [items, setItems] = useState<DraftImage[]>([])
  const [error, setError] = useState('')
  const [reading, setReading] = useState(false)
  const current = useRef(items)
  const alive = useRef(true)
  const selecting = useRef(false)
  const auth = useRef(authProvider)
  auth.current = authProvider
  const change = (next: DraftImage[]) => { current.current = next; if (alive.current) setItems(next) }
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; current.current = [] }
  }, [])
  useEffect(() => {
    let valid = true
    setEnabled(false)
    change([])
    setError('')
    if (enabledSession) {
      try {
        void wowApi.chat.imageCapabilities({auth: auth.current()}).then(result => {
          if (valid) setEnabled(!result.fromFallback && result.payload.enabled)
        }).catch(() => undefined)
      } catch { /* Session is not ready yet. */ }
    } else change([])
    return () => { valid = false }
  }, [enabledSession, sessionKey])
  const upload = async (item: DraftImage) => {
    if (!current.current.some(row => row.key === item.key)) return
    change(current.current.map(row => row.key === item.key ? {...row, status: 'uploading'} : row))
    try {
      const context = auth.current()
      const result = await wowApi.chat.uploadImage({dataUrl: item.dataUrl}, {auth: context, idempotencyKey: item.key})
      if (result.fromFallback) throw new Error(result.error || '上传失败，请重试')
      if (!alive.current || !current.current.some(row => row.key === item.key)) {
        void wowApi.chat.removeImage(result.payload.id, {auth: context}).catch(() => undefined)
        return
      }
      change(current.current.map(row => row.key === item.key ? {...row, status: 'ready', image: result.payload} : row))
    } catch (failure) {
      change(current.current.map(row => row.key === item.key ? {...row, status: 'failed'} : row))
      if (alive.current) setError(failure instanceof Error ? failure.message : '上传失败，请重试')
    }
  }
  const remove = (key: string) => {
    const item = current.current.find(row => row.key === key)
    setError('')
    change(current.current.filter(row => row.key !== key))
    if (item?.image) {
      try { void wowApi.chat.removeImage(item.image.id, {auth: auth.current()}).catch(() => undefined) } catch { /* Expiry cleans unattached images. */ }
    }
  }
  const add = async (read: (count: number) => Promise<string[]>) => {
    if (!enabled || !alive.current) return
    if (selecting.current) { setError('图片正在读取，请稍候再试'); return }
    if (current.current.length >= 3) { setError('每条消息最多三张图片，请先移除部分图片'); return }
    selecting.current = true
    setReading(true)
    setError('')
    try {
      const selectedSession = auth.current()
      const urls = await read(3 - current.current.length)
      if (!alive.current) return
      const latestSession = auth.current()
      if (JSON.stringify(selectedSession) !== JSON.stringify(latestSession)) return
      if (urls.length + current.current.length > 3) throw new Error('每条消息最多三张图片，请先移除部分图片')
      const added: DraftImage[] = urls.map(dataUrl => ({
        key: `chat-image-${Date.now()}-${++sequence}`, dataUrl, status: 'uploading',
      }))
      change([...current.current, ...added])
      added.forEach(item => { void upload(item) })
    } catch (failure) {
      if (alive.current) setError(failure instanceof Error ? failure.message : '图片选择未完成')
    } finally { selecting.current = false; if (alive.current) setReading(false) }
  }
  return {
    enabled, items, error, pending: reading || items.some(item => item.status !== 'ready'),
    images: items.flatMap(item => item.image ? [item.image] : []),
    clear: () => { const sentKeys = new Set(items.map(item => item.key)); change(current.current.filter(item => !sentKeys.has(item.key))) },
    discard: () => current.current.forEach(item => remove(item.key)),
    remove,
    retry: (key: string) => { const item = current.current.find(row => row.key === key); if (item?.status === 'failed') { setError(''); void upload(item) } },
    add,
    choose: () => add(chooseChatImages),
  }
}
