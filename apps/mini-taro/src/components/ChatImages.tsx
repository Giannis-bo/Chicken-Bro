import { Button, Image, Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { wowApi, type ClientAuthContext } from '@wow-mini/api-client'
import type { ChatImage } from '@wow-mini/domain'
import type { DraftImage } from '../features/chat/use-chat-images'
import { useImageSource } from '../features/chat/use-image-source'
import ChatImageOverlay from './ChatImageOverlay'
import styles from './ChatImages.module.scss'

function Preview({src}: {src: string}) {
  const {source, failed, retry} = useImageSource(src)
  const [expanded, setExpanded] = useState(false)
  if (failed) return <Button onClick={retry}>图片准备失败，重试</Button>
  if (!source) return <Text>图片准备中…</Text>
  return <>
    <Button className={styles['thumbnail'] ?? ''} aria-label="预览图片" onClick={() => setExpanded(true)}>
      <Image src={source} mode="aspectFit" className={styles['image'] ?? ''} />
    </Button>
    {expanded ? <ChatImageOverlay><View className={styles['overlay'] ?? ''}>
      <Button className={styles['close'] ?? ''} onClick={() => setExpanded(false)}>关闭预览</Button>
      <Image src={source} mode="aspectFit" className={styles['expanded'] ?? ''} />
    </View></ChatImageOverlay> : null}
  </>
}
function HistoryImage({image, auth}: {image: ChatImage; auth: ClientAuthContext}) {
  const [src, setSrc] = useState('')
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (attempt === 0) return
    let valid = true
    setSrc('')
    setFailed(false)
    void wowApi.chat.getImage(image.id, {auth}).then(result => {
      if (!valid) return
      if (result.fromFallback) setFailed(true)
      else setSrc(result.payload.dataUrl)
    }).catch(() => { if (valid) setFailed(true) })
    return () => { valid = false }
  }, [image.id, auth, attempt])
  if (attempt === 0) return <Button onClick={() => setAttempt(1)}>查看图片</Button>
  return src ? <Preview src={src} /> : failed
    ? <Button onClick={() => setAttempt(value => value + 1)}>图片加载失败，重试</Button>
    : <Text>图片加载中…</Text>
}
export function ChatImages({images, auth}: {images?: readonly ChatImage[] | undefined; auth: ClientAuthContext}) {
  return images?.length ? <View className={styles['row'] ?? ''}>{images.map(image =>
    <HistoryImage key={image.id} image={image} auth={auth} />)}</View> : null
}
export function ChatImageDrafts({items, disabled, remove, retry, compact = false}: {
  items: readonly DraftImage[]; disabled: boolean; remove: (key: string) => void; retry: (key: string) => void; compact?: boolean
}) {
  if (compact) return items.length ? <div className={styles['draftRow']} aria-label="待发送图片">{items.map(item => <div className={styles['draftItem']} key={item.key}>
    <Preview src={item.dataUrl} />
    <button type="button" className={styles['remove']} aria-label="移除图片" title="移除图片" disabled={disabled} onClick={() => remove(item.key)}>×</button>
    {item.status === 'failed' ? <button type="button" className={styles['retry']} disabled={disabled} onClick={() => retry(item.key)}>重试上传</button>
      : <span className={styles[item.status === 'ready' ? 'ready' : 'uploading']} role="status">{item.status === 'ready' ? '已就绪' : '上传中…'}</span>}
  </div>)}</div> : null
  return items.length ? <View className={styles['row'] ?? ''}>{items.map(item => <View key={item.key}>
    <Preview src={item.dataUrl} />
    <Text className={styles['status'] ?? ''}>{item.status === 'uploading' ? '上传中…' : item.status === 'failed' ? '上传失败' : '已就绪'}</Text>
    {item.status === 'failed' ? <Button className={styles['action'] ?? ''} size="mini" disabled={disabled} onClick={() => retry(item.key)}>重试上传</Button> : null}
    <Button className={styles['action'] ?? ''} size="mini" disabled={disabled} onClick={() => remove(item.key)}>移除图片</Button>
  </View>)}</View> : null
}
