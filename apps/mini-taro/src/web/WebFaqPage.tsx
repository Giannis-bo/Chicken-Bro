import { useEffect, useRef } from 'react'

import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import styles from './WebFaqPage.module.scss'

const questions = [
  ['能用鸡哥做什么？', '可以讨论魔兽世界的副本、装备和输出问题，也可以提交角色来源链接，创建云端 SIMC 模拟任务。提供具体问题、角色或战斗日志链接，有助于鸡哥展开分析。'],
  ['Web 和小程序的记录会同步吗？', '使用同一个账号登录后，两端可以查看并继续同一段对话，也能查看同一模拟任务的状态和结果。若记录不同，先检查是否登录了同一账号。'],
  ['模拟支持哪些角色来源？', '在“模拟”中粘贴 HTTPS 的 Raider.IO 角色链接或 Warcraft Logs 链接，国服战斗日志链接也可使用。链接格式请参考提交页的示例；当前不支持直接粘贴插件 /simc 导出的文本。'],
  ['角色资料不完整或模拟失败怎么办？', '先根据页面提示检查链接和缺失字段，补充可用来源后重试。来源未提供的装备、天赋等信息不会自动猜测；失败任务的原因可在任务详情中查看。'],
  ['模拟中的数值和名称怎么看？', '任务详情会展示本次模拟的结果、误差和版本信息。中文名称仍在逐步补齐，尚未收录的名称可能保留英文，不影响阅读对应的模拟数值。'],
  ['退出登录会删除记录吗？', '不会。对话和模拟记录仍保留在当前账号下，重新登录同一账号后可以继续查看。Web 与小程序分别登录和退出。'],
]


const groups = [
  { title: '认识鸡哥', description: '从这里开始', questions: [questions[0]!] },
  { title: '账号与记录', description: '登录、同步与退出', questions: [questions[1]!, questions[5]!] },
  { title: 'SIMC 模拟', description: '角色来源与结果', questions: [questions[2]!, questions[3]!, questions[4]!] },
]

export default function WebFaqPage({ returnLabel, onReturn }: { returnLabel: string; onReturn: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    const previousScroll = window.scrollY
    headingRef.current?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
    return () => window.scrollTo(0, previousScroll)
  }, [])
  return (
    <main className={styles['page']} aria-labelledby="web-faq-title">
      <div className={styles['content']}>
        <button type="button" className={styles['back']} aria-label={returnLabel} onClick={onReturn}>
          <span aria-hidden="true">←</span> {returnLabel}
        </button>
        <header className={styles['header']}>
          <span className={styles['eyebrow']}>使用帮助</span>
          <h1 ref={headingRef} tabIndex={-1} id="web-faq-title">FAQ</h1>
          <p>从登录到第一份模拟结果，常见问题都在这里。</p>
        </header>
        {isTestLoginEnabled() ? (
          <div className={styles['testNote']}>你正在使用测试版。选择 A / B 测试账号并输入对应凭证登录，两端请选同一个账号。</div>
        ) : null}
        {groups.map(group => (
          <section className={styles['group']} key={group.title} aria-label={group.title}>
            <div className={styles['groupTitle']}><h2>{group.title}</h2><p>{group.description}</p></div>
            <div className={styles['answers']}>
              {group.questions.map(([question, answer]) => (
                <article key={question} className={styles['answer']}><h3>{question}</h3><p>{answer}</p></article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  )
}
