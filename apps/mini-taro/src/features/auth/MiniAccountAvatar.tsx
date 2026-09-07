import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useCallback, useEffect, useRef, useState } from 'react'
import { wowApi } from '@wow-mini/api-client'
import styles from './MiniAccountAvatar.module.scss'

/** chooseAvatar returns a temporary path. Upload bytes, never that device path. */
export async function readChosenAvatar(path: string): Promise<string> {
  const compressed = await Taro.compressImage({ src: path, quality: 75, compressedWidth: 256, compressedHeight: 256 })
  const content = await new Promise<string>((resolve, reject) => {
    Taro.getFileSystemManager().readFile({ filePath: compressed.tempFilePath, encoding: 'base64',
      success: result => typeof result.data === 'string' ? resolve(result.data) : reject(new Error('AVATAR_READ_FAILED')),
      fail: reject,
    })
  })
  if (content.length > 349528) throw new Error('AVATAR_TOO_LARGE')
  const kind = content.startsWith('iVBORw0KGgo') ? 'png' : content.startsWith('/9j/') ? 'jpeg' : ''
  if (!kind) throw new Error('AVATAR_FORMAT')
  return `data:image/${kind};base64,${content}`
}

export default function MiniAccountAvatar({ accessToken, iconOnly = false }: { accessToken: string; iconOnly?: boolean }) {
  const [avatar, setAvatar] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const generation = useRef(0)
  const busy = useRef(false)
  const refresh = useCallback(async () => {
    const current = ++generation.current
    try {
      const result = await wowApi.avatar.get({ kind: 'mini', accessToken })
      if (current === generation.current && !result.fromFallback) setAvatar(result.payload.avatarDataUrl)
    } catch { /* Optional account decoration never blocks the page. */ }
  }, [accessToken])
  useEffect(() => {
    setAvatar(null)
    void refresh()
    return () => { generation.current += 1 }
  }, [refresh])
  useDidShow(() => { if (!busy.current) void refresh() })

  return <View className={`${styles['account'] ?? ''} ${iconOnly ? styles['iconOnly'] ?? '' : ''}`} >
    <Button className={styles['choose'] ?? ''} size="mini" openType="chooseAvatar" disabled={saving} ariaLabel={saving ? '保存中' : avatar ? '更换头像' : '选择头像'}
      onChooseAvatar={event => {
        const path = event.detail.avatarUrl
        if (!path || busy.current) return
        busy.current = true
        setSaving(true)
        setMessage('')
        const current = ++generation.current
        void (async () => {
          try {
            const image = await readChosenAvatar(path)
            if (current !== generation.current) return
            const result = await wowApi.avatar.set(image, { kind: 'mini', accessToken })
            if (current !== generation.current) return
            if (result.fromFallback) throw new Error('AVATAR_SAVE_FAILED')
            setAvatar(result.payload.avatarDataUrl)
            setMessage('已保存，Web 也会显示')
          } catch (error) {
            if (current === generation.current) {
              const failure = error instanceof Error && error.message === 'AVATAR_TOO_LARGE'
                ? '图片较大，请换一张再试' : '头像未保存，请重试'
              setMessage(failure)
              if (iconOnly) void Taro.showToast({ title: failure, icon: 'none' })
            }
          } finally {
            busy.current = false
            if (current === generation.current) setSaving(false)
          }
        })()
      }}>
      {avatar ? <Image className={styles['image'] ?? ''} src={avatar} mode="aspectFill" onError={() => setAvatar(null)} /> : <Text className={styles['placeholder'] ?? ''}>我</Text>}
      {iconOnly ? <Text className={styles['editBadge'] ?? ''}>{saving ? '…' : message === '已保存，Web 也会显示' ? '✓' : '✎'}</Text> : <Text>{saving ? '保存中…' : avatar ? '更换头像' : '设置头像'}</Text>}
    </Button>
    {message && !iconOnly ? <Text className={styles['message'] ?? ''}>{message}</Text> : null}
  </View>
}
