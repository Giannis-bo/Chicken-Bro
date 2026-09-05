import { Button, Input, Text, View } from '@tarojs/components'
import { useRef, useState } from 'react'

import styles from './test-login.module.scss'

interface TestLoginFormProps {
  onLogin: (account: 'A' | 'B', credential: string) => Promise<void>
}

const errorCopy: Record<string, string> = {
  AUTH_REQUIRED: '测试凭证不正确，请检查所选账号和凭证',
  NOT_FOUND: '当前服务未开放测试登录，请检查测试环境地址',
  TEST_LOGIN_DISABLED: '当前服务未开放测试登录',
  ORIGIN_REJECTED: '页面地址与测试服务配置不匹配',
  IDENTITY_CONFLICT: '测试账号不可用，请联系管理员',
}

export default function TestLoginForm({ onLogin }: TestLoginFormProps) {
  const [account, setAccount] = useState<'A' | 'B'>('A')
  const [credential, setCredential] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)

  const submit = async () => {
    if (pending.current || credential.length < 32) return
    pending.current = true
    setBusy(true)
    setError('')
    const value = credential
    setCredential('')
    try {
      await onLogin(account, value)
    } catch (reason) {
      const code = reason instanceof Error ? reason.message : ''
      setError(errorCopy[code] ?? '测试登录未完成，请检查网络后重新输入凭证')
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return (
    <View className={styles['card'] ?? ''}>
      <Text className={styles['title'] ?? ''}>测试账号登录</Text>
      <Text className={styles['hint'] ?? ''}>免微信确认 · 真实聊天与 SimC · 独立测试数据</Text>
      <View className={styles['accounts'] ?? ''}>
        {(['A', 'B'] as const).map((value) => (
          <Button key={value} size="mini" disabled={busy} data-selected={account === value}
            onClick={() => { setAccount(value); setCredential(''); setError('') }}>
            测试账号 {value}{account === value ? ' ✓' : ''}
          </Button>
        ))}
      </View>
      <Input className={styles['input'] ?? ''} password value={credential} maxlength={256}
        disabled={busy} placeholder={`输入测试账号 ${account} 的凭证`}
        onInput={(event) => setCredential(event.detail.value)} onConfirm={() => void submit()} />
      <Button className={styles['submit'] ?? ''} disabled={busy || credential.length < 32}
        onClick={() => void submit()}>{busy ? '正在连接…' : `以测试账号 ${account} 进入`}</Button>
      {error ? <Text className={styles['error'] ?? ''}>{error}</Text> : null}
      <Text className={styles['hint'] ?? ''}>两端选同一账号可共享历史。会话保留至退出或过期，凭证不会保存到客户端。</Text>
    </View>
  )
}
