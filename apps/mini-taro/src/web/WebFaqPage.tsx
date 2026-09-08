import { useEffect, useRef } from 'react'

import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import { faqGroups } from '../features/help/faq-content'
import styles from './WebFaqPage.module.scss'


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
        </header>
        {isTestLoginEnabled() ? (
          <div className={styles['testNote']}>你正在使用测试版。选择 A / B 测试账号并输入对应凭证登录，两端请选同一个账号。</div>
        ) : null}
        {faqGroups.map((group, index) => (
          <details className={styles['group']} key={group.title}>
            <summary className={styles['groupTitle']}>
              <span><h2>{group.title}</h2><span className={styles['description']}>{group.description}</span></span>
              <span className={styles['chevron']} aria-hidden="true">⌄</span>
            </summary>
            <div className={styles['answers']}>
              {group.note ? <p className={styles['caseNote']}>{group.note}</p> : null}
              {group.items.map(item => (
                <article key={item.question} className={styles['answer']}>
                  <h3>{item.question}</h3>
                  {item.prompt ? <div className={styles['prompt']}><h4>可以这样问</h4><p>{item.prompt}</p></div> : null}
                  {item.prompt ? <h4>{index === 1 ? '当时得到的结果' : '鸡哥会怎么做'}</h4> : null}
                  <p>{item.answer}</p>
                </article>
              ))}
            </div>
          </details>
        ))}
      </div>
    </main>
  )
}
