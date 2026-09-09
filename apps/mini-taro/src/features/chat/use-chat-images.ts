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
    change(current.current.filter(row => row.key !== key))
    if (item?.image) {
      try { void wowApi.chat.removeImage(item.image.id, {auth: auth.current()}).catch(() => undefined) } catch { /* Expiry cleans unattached images. */ }
    }
  }
  return {
    enabled, items, error, pending: items.some(item => item.status !== 'ready'),
    images: items.flatMap(item => item.image ? [item.image] : []),
    clear: () => { const sentKeys = new Set(items.map(item => item.key)); change(current.current.filter(item => !sentKeys.has(item.key))) },
    discard: () => current.current.forEach(item => remove(item.key)),
    remove,
    retry: (key: string) => { const item = current.current.find(row => row.key === key); if (item?.status === 'failed') void upload(item) },
    choose: async () => {
      if (!enabled || selecting.current || current.current.length >= 3) return
      selecting.current = true
      setError('')
      try {
        const selectedSession = auth.current()
        const urls = await chooseChatImages(3 - current.current.length)
        if (!alive.current) return
        const latestSession = auth.current()
        if (JSON.stringify(selectedSession) !== JSON.stringify(latestSession)) return
        const added: DraftImage[] = urls.slice(0, 3 - current.current.length).map(dataUrl => ({
          key: `chat-image-${Date.now()}-${++sequence}`, dataUrl, status: 'uploading',
        }))
        change([...current.current, ...added])
        added.forEach(item => { void upload(item) })
      } catch (failure) {
        if (alive.current) setError(failure instanceof Error ? failure.message : '图片选择未完成')
      } finally { selecting.current = false }
    },
  }
}
