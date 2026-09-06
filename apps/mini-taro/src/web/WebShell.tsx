import { Button, Text, View } from '@tarojs/components'
import { useState } from 'react'

import type { ClientAuthContext } from '@wow-mini/api-client'

import WebChatView from './WebChatView'
import WebSimcView from './WebSimcView'
import WebServiceHealth from './WebServiceHealth'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type BusinessView = 'chat' | 'simc'

const modes: Array<{ id: BusinessView; number: string; label: string }> = [
  { id: 'chat', number: '01', label: '对话' },
  { id: 'simc', number: '02', label: '模拟' },
]

export interface WebShellProps {
  accountLabel: string
  auth: WebClientAuth
  onLogout: () => void
}

export default function WebShell({ accountLabel, auth, onLogout }: WebShellProps) {
  const [activeView, setActiveView] = useState<BusinessView>('chat')
  const [isHordeSkin, setIsHordeSkin] = useState(true)

  return (
    <View
      className={styles['workspace'] ?? ''}
      data-business-view={activeView}
      data-skin={isHordeSkin ? 'horde' : 'clean'}
    >
      <View className={styles['workspaceTopbar'] ?? ''}>
        <View className={styles['brand'] ?? ''}>
          <View className={styles['brandMascotFrame'] ?? ''}>
            <View className={styles['brandMascot'] ?? ''} />
          </View>
          <View className={styles['brandCopy'] ?? ''}>
            <Text className={styles['brandName'] ?? ''}>炸鸡队长来啦</Text>
          </View>
          <WebServiceHealth />
        </View>

        <View className={styles['modeSwitch'] ?? ''}>
          {modes.map((mode) => (
            <Button
              key={mode.id}
              className={styles['navButton'] ?? ''}
              data-active={activeView === mode.id ? 'true' : 'false'}
              aria-label={mode.id === 'simc' ? 'SimC 模拟' : '队长对话'}
              onClick={() => setActiveView(mode.id)}
            >
              <Text className={styles['modeSwitchNumber'] ?? ''}>{mode.number}</Text>
              <Text>{mode.label}</Text>
            </Button>
          ))}
        </View>

        <View className={styles['headerActions'] ?? ''}>
          <Button
            className={styles['skinToggle'] ?? ''}
            data-active={isHordeSkin ? 'true' : 'false'}
            aria-pressed={isHordeSkin}
            onClick={() => setIsHordeSkin((current) => !current)}
          >
            <View className={styles['skinToggleDot'] ?? ''} />
            <Text className={styles['skinToggleLabel'] ?? ''}>
              {isHordeSkin ? '为了部落！' : '开启主题'}
            </Text>
          </Button>
          <View className={styles['accountBlock'] ?? ''}>
            <Text className={styles['accountLabel'] ?? ''}>{accountLabel}</Text>
            <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={onLogout}>
              退出
            </Button>
          </View>
        </View>
      </View>

      <View className={styles['workspaceBody'] ?? ''}>
        <View className={styles['workspaceMain'] ?? ''}>
          {activeView === 'chat' && isHordeSkin ? (
            <View className={styles['workspaceArt'] ?? ''} data-decorative="true">
              <View className={styles['chatArtCrop'] ?? ''}>
                <View className={styles['chatScene'] ?? ''} />
                <View className={styles['chatArtWash'] ?? ''} />
                <View className={`${styles['chatCloud'] ?? ''} ${styles['chatCloudBack'] ?? ''}`} />
                <View className={`${styles['chatCloud'] ?? ''} ${styles['chatCloudFront'] ?? ''}`} />
              </View>
            </View>
          ) : null}

          {activeView === 'chat'
            ? <WebChatView auth={auth} showHordeSkin={isHordeSkin} />
            : <WebSimcView auth={auth} />}
        </View>
      </View>
    </View>
  )
}
