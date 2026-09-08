import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { wowApi } from '@wow-mini/api-client'
import MiniAccountAvatar from './MiniAccountAvatar'
import MiniThemePicker from '../theme/MiniThemePicker'
import styles from './MiniAccountPanel.module.scss'

export default function MiniAccountPanel({ accessToken, onClose, onSignOut }: {
  accessToken: string; onClose: () => void; onSignOut: () => Promise<void>
}) {
  const [name, setName] = useState('正在读取账号…')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let current = true
    setError('')
    void wowApi.webAuth.me({ kind: 'mini', accessToken }).then(result => {
      if (!current) return
      if (result.fromFallback) { setName('账号信息暂不可用'); setError('请重试读取账号') }
      else setName(result.payload.displayName || '已连接微信账号')
    }).catch(() => { if (current) { setName('账号信息暂不可用'); setError('请重试读取账号') } })
    return () => { current = false }
  }, [accessToken, refresh])
  const signOut = async () => {
    if (busy) return
    setBusy(true)
    try {
      const answer = await Taro.showModal({ title: '退出登录', content: '退出当前小程序账号？聊天和模拟记录会保留，Web 登录不受影响。', confirmText: '退出' })
      if (answer.confirm) await onSignOut()
    } catch { setError('退出未完全确认，请检查网络后重试') }
    finally { setBusy(false) }
  }
  return <View className={styles['panel'] ?? ''}>
    <View className={styles['header'] ?? ''}><Text className={styles['title'] ?? ''}>账号与外观</Text><Button onClick={onClose}>返回</Button></View>
    <ScrollView scrollY className={styles['scroll'] ?? ''}>
      <View className={styles['card'] ?? ''}>
        <Text className={styles['caption'] ?? ''}>当前账号</Text><Text selectable className={styles['name'] ?? ''}>{name}</Text>
        <MiniAccountAvatar accessToken={accessToken} />
        {error ? <><Text className={styles['error'] ?? ''}>{error}</Text><Button onClick={() => setRefresh(n => n + 1)}>重试读取</Button></> : null}
      </View>
      <View className={styles['card'] ?? ''}><MiniThemePicker /></View>
      <View className={styles['card'] ?? ''}>
        <Text className={styles['caption'] ?? ''}>聊天和模拟记录由当前微信账号共享；Web 和小程序分别登录。</Text>
        <Button className={styles['logout'] ?? ''} disabled={busy} onClick={() => void signOut()}>{busy ? '正在处理…' : '退出登录'}</Button>
      </View>
    </ScrollView>
  </View>
}
