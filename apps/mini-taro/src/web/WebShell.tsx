import { Button, Text, View } from '@tarojs/components'
import { useState } from 'react'

import type { ClientAuthContext } from '@wow-mini/api-client'

import WebChatView from './WebChatView'
import WebSimcView from './WebSimcView'
import styles from './WebApp.module.scss'


type WebClientAuth = Extract<ClientAuthContext, { kind: 'web' }>
type BusinessView = 'chat' | 'simc'

export interface WebShellProps {
  accountLabel: string
  auth: WebClientAuth
  onLogout: () => void
}

export default function WebShell({ accountLabel, auth, onLogout }: WebShellProps) {
  const [activeView, setActiveView] = useState<BusinessView>('chat')

  return (
    <View className={styles['workspace'] ?? ''} data-business-view={activeView}>
      <View className={styles['workspaceTopbar'] ?? ''}>
        <View className={styles['brand'] ?? ''}>
          <View className={styles['brandMark'] ?? ''}>CB</View>
          <View>
            <Text className={styles['brandName'] ?? ''}>CHICKENBRO</Text>
            <Text className={styles['brandMeta'] ?? ''}>队长会话 · SimC 任务</Text>
          </View>
        </View>
        <View className={styles['accountRow'] ?? ''}>
          <Text className={styles['accountLabel'] ?? ''}>{accountLabel}</Text>
          <Button className={styles['secondaryButton'] ?? ''} size="mini" onClick={onLogout}>
            退出登录
          </Button>
        </View>
      </View>

      <View className={styles['workspaceBody'] ?? ''}>
        <View className={styles['workspaceNav'] ?? ''}>
          <Button
            className={styles['navButton'] ?? ''}
            data-active={activeView === 'chat' ? 'true' : 'false'}
            onClick={() => setActiveView('chat')}
          >
            队长
          </Button>
          <Button
            className={styles['navButton'] ?? ''}
            data-active={activeView === 'simc' ? 'true' : 'false'}
            onClick={() => setActiveView('simc')}
          >
            SimC
          </Button>
        </View>

        <View className={styles['workspaceMain'] ?? ''}>
          {activeView === 'chat'
            ? <WebChatView auth={auth} />
            : <WebSimcView auth={auth} />}
        </View>
      </View>
    </View>
  )
}
