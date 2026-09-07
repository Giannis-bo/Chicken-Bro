import { createContext, useContext } from 'react'
import Taro from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import styles from './MiniHelp.module.scss'

export type MiniHelpView = 'faq' | 'changelog'

// Mini copy follows the same product topics as Web, with platform-specific
// capabilities labelled explicitly. Web's components and content stay untouched.
const questions = [
  { title: '认识鸡哥', items: [
    ['能用鸡哥做什么？', '可以讨论魔兽世界的副本、装备和输出问题，也可以提交角色来源链接，创建云端 SimC 模拟任务。提供具体问题、角色或战斗日志链接，有助于鸡哥展开分析。'],
  ] },
  { title: '账号与记录', items: [
    ['Web 和小程序的记录会同步吗？', '使用同一个账号登录后，两端可以查看并继续同一段对话，也能查看同一模拟任务的状态和结果。若记录不同，先检查是否登录了同一账号。'],
    ['退出登录会删除记录吗？', '不会。对话和模拟记录仍保留在当前账号下，重新登录同一账号后可以继续查看。Web 与小程序分别登录和退出。'],
  ] },
  { title: 'SimC 模拟', items: [
    ['模拟支持哪些角色来源？', '在 SimC 中粘贴 HTTPS 的 Raider.IO 角色页或 Warcraft Logs 角色链接，国服战斗日志链接也可使用。先读取角色，再设置目标数和迭代次数；当前不支持直接粘贴插件 /simc 导出的文本。'],
    ['角色资料不完整或模拟失败怎么办？', '先根据页面提示检查链接和缺失字段，补充可用来源后重试。来源未提供的装备、天赋等信息不会自动猜测；失败原因可在任务详情查看。改了角色链接后，需要重新读取资料。'],
    ['模拟中的数值和名称怎么看？', '小程序任务详情先展示本次模拟的数值与技能、增益信息，版本和来源信息可展开“运行详情”查看。中文名称仍在逐步补齐，未收录的名称可能保留英文。'],
  ] },
  { title: '手机阅读与输入', items: [
    ['如何查看历史、复制回复和来源链接？', '点击“历史对话”选择会话；长按回复文字可以选择复制，点击带箭头的来源链接可复制地址，再粘贴到浏览器查看。输入区支持多行文字。'],
    ['打开帮助会丢失草稿或中断回复吗？', '不会。FAQ 和更新日志会保留当前页面，关闭帮助后可继续输入；正在生成的回复也会继续接收。'],
  ] },
] as const
const releases = [
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
  return <Button className={styles['more'] ?? ''} aria-label="更多：帮助与更新" onClick={() => void openMenu()}>更多</Button>
}

export function MiniHelpPanel({ view, onClose }: { view: MiniHelpView; onClose: () => void }) {
  return <View className={styles['panel'] ?? ''}>
    <View className={styles['header'] ?? ''}>
      <Text className={styles['title'] ?? ''}>{view === 'faq' ? 'FAQ · 常见问题' : '更新日志'}</Text>
      <Button className={styles['close'] ?? ''} size="mini" onClick={onClose}>关闭帮助</Button>
    </View>
    <ScrollView key={view} className={styles['scroll'] ?? ''} scrollY>
      <View className={styles['content'] ?? ''}>
        {view === 'faq' ? <>
          {isTestLoginEnabled() ? <Text className={styles['note'] ?? ''}>你正在使用测试版。选择 A / B 测试账号并输入对应凭证登录，两端请选同一个账号。</Text> : null}
          {questions.map((group) => <View key={group.title} className={styles['group'] ?? ''}>
            <Text className={styles['groupTitle'] ?? ''}>{group.title}</Text>
            {group.items.map(([question, answer]) => <View key={question} className={styles['item'] ?? ''}>
              <Text className={styles['question'] ?? ''}>{question}</Text>
              <Text selectable className={styles['answer'] ?? ''}>{answer}</Text>
            </View>)}
          </View>)}
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
