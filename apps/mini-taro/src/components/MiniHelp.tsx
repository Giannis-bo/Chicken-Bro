import { createContext, useContext, useState } from 'react'
import Taro from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import { faqGroups } from '../features/help/faq-content'
import styles from './MiniHelp.module.scss'

export type MiniHelpView = 'faq' | 'changelog'

const releases = [
  { date: '2026-09-08', scope: '小程序 / Web', title: '炸鸡队长来啦 1.0 正式上线', items: [
    '与鸡哥聊魔兽、运行云端模拟，在小程序和 Web 继续同一段对话。',
  ] },
  { date: '2026-09-07', scope: '小程序', title: '小程序移动端交互优化', items: [
    '调整顶部安全区与底部导航，聊天输入区常驻。',
    '历史对话改为折叠列表，回复支持 Markdown 和纵向时间线。',
    '补充首次直接发送、等待提示与草稿保护。',
    '模拟增加参数校验，结果前置，运行信息按需展开。',
    '新增 FAQ 和更新日志入口，聊天、模拟及登录页均可查看。',
  ] },
  { date: '2026-09-07', scope: 'Web', title: 'Web 导航与帮助入口', items: [
    '头像菜单显示当前账号，支持退出登录。',
    'FAQ 使用独立页面，支持直接链接和浏览器返回；更新日志随时可查。',
    '精简侧栏装饰与主题口号。',
  ] },
  { date: '2026-09-06', scope: '模拟与报告', title: '模拟工作台与报告升级', items: [
    'Web 新增模拟参数、任务列表与结构化结果展示。',
    '改进国服角色和战斗日志导入，逐步补齐技能、召唤物及增益的中文名称。',
    '鸡哥可以按需发起云端模拟；同账号两端可查看任务结果。',
  ] },
  { date: '2026-09-05', scope: 'Web', title: '聊天阅读和历史记录优化', items: [
    '历史对话按日期分组，支持展开和收起。',
    '优化回复排版、文字选择、输入区与等待提示。',
    '长回复自动跟随，上翻或选择文字时暂停跟随。',
  ] },
]

export const MiniHelpContext = createContext<(view: MiniHelpView) => void>(() => undefined)

export function MiniHelpActions() {
  const onOpen = useContext(MiniHelpContext)
  const openMenu = async () => {
    try {
      const { tapIndex } = await Taro.showActionSheet({ itemList: ['FAQ · 常见问题', '更新日志'] })
      if (tapIndex === 0 || tapIndex === 1) onOpen(tapIndex === 0 ? 'faq' : 'changelog')
    } catch { /* Dismissing the native menu leaves the current page untouched. */ }
  }
  return <Button className={styles['more'] ?? ''} aria-label="更多：FAQ 与更新日志" onClick={() => void openMenu()}>更多</Button>
}

export function MiniHelpPanel({ view, onClose }: { view: MiniHelpView; onClose: () => void }) {
  const [openGroups, setOpenGroups] = useState<string[]>([])
  return <View className={styles['panel'] ?? ''}>
    <View className={styles['header'] ?? ''}>
      <Text className={styles['title'] ?? ''}>{view === 'faq' ? 'FAQ · 常见问题' : '更新日志'}</Text>
      <Button className={styles['close'] ?? ''} size="mini" onClick={onClose}>关闭帮助</Button>
    </View>
    <ScrollView key={view} className={styles['scroll'] ?? ''} scrollY>
      <View className={styles['content'] ?? ''}>
        {view === 'faq' ? <>
          {isTestLoginEnabled() ? <Text className={styles['note'] ?? ''}>你正在使用测试版。选择 A / B 测试账号并输入对应凭证登录，两端请选同一个账号。</Text> : null}
          {faqGroups.map((group, index) => {
            const open = openGroups.includes(group.title)
            return <View key={group.title} className={styles['group'] ?? ''}>
              <Button className={styles['groupToggle'] ?? ''} aria-label={group.title} aria-expanded={open} onClick={() => setOpenGroups(current => open ? current.filter(title => title !== group.title) : [...current, group.title])}>
                <View><Text className={styles['groupTitle'] ?? ''}>{group.title}</Text><Text className={styles['description'] ?? ''}>{group.description}</Text></View>
                <Text>{open ? '收起 −' : '展开 +'}</Text>
              </Button>
              {open ? <View>
                {group.note ? <Text selectable className={styles['note'] ?? ''}>{group.note}</Text> : null}
                {group.items.map(item => <View key={item.question} className={styles['item'] ?? ''}>
                  <Text selectable className={styles['question'] ?? ''}>{item.question}</Text>
                  {item.prompt ? <View className={styles['prompt'] ?? ''}><Text selectable className={styles['meta'] ?? ''}>可以这样问</Text><Text selectable className={styles['answer'] ?? ''}>{item.prompt}</Text></View> : null}
                  {item.prompt ? <Text selectable className={styles['meta'] ?? ''}>{index === 1 ? '当时得到的结果' : '鸡哥会怎么做'}</Text> : null}
                  <Text selectable className={styles['answer'] ?? ''}>{item.answer}</Text>
                </View>)}
              </View> : null}
            </View>
          })}
        </> : <>
          <Text className={styles['note'] ?? ''}>{isTestLoginEnabled() ? '以下记录近期测试版更新，正式版上线时间另行记录。每条更新已标明适用端。' : '以下记录各功能的更新日期，本次正式版已包含这些改进。每条更新已标明适用端。'}</Text>
          {releases.map((release) => <View key={`${release.date}-${release.title}`} className={styles['item'] ?? ''}>
            <Text className={styles['meta'] ?? ''}>{release.date} · {release.scope} · {isTestLoginEnabled() ? '测试版' : '功能更新'}</Text>
            <Text className={styles['question'] ?? ''}>{release.title}</Text>
            {release.items.map((item) => <Text key={item} className={styles['answer'] ?? ''}>• {item}</Text>)}
          </View>)}
        </>}
      </View>
    </ScrollView>
  </View>
}
