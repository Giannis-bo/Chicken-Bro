import { Text, View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMemo } from 'react'
import { miniInlineTokens, miniMarkdownBlocks } from '../features/chat/mini-markdown'
import styles from './MiniMessage.module.scss'

function Inline({ content }: { content: string }) {
  return <Text selectable className={styles['text'] ?? ''}>
    {miniInlineTokens(content).map((token, index) => <Text key={index} className={styles[token.kind] ?? ''}
      onClick={() => { if (!token.url) return; void Taro.setClipboardData({ data: token.url! }).catch(() => Taro.showToast({ title: '复制失败，请重试', icon: 'none' })) }}
    >{token.content}{token.kind === 'link' ? ' ↗' : ''}</Text>)}
  </Text>
}

export default function MiniMessage({ content, markdown = false }: { content: string; markdown?: boolean }) {
  const blocks = useMemo(() => markdown ? miniMarkdownBlocks(content) : [], [content, markdown])
  if (!markdown) return <Text selectable className={styles['text'] ?? ''}>{content}</Text>
  return <View className={styles['root'] ?? ''}>
    {blocks.map((block, index) => block.kind === 'table'
      ? <View key={index} className={styles['table'] ?? ''}>
        {block.rows.map((row, r) => <View key={r} className={styles['tableRow'] ?? ''}>
          {row.map((cell, c) => <View key={c} className={styles['tableCell'] ?? ''}>
            <Text className={styles['tableLabel'] ?? ''}>{block.headers[c] || `第 ${c + 1} 列`}</Text>
            <Inline content={cell} />
          </View>)}
        </View>)}
      </View>
      : <View key={index} className={styles[block.kind] ?? ''}>
        {block.kind === 'code' ? <Text selectable className={styles['text'] ?? ''}>{block.content}</Text> : <Inline content={block.content} />}
      </View>)}
  </View>
}
