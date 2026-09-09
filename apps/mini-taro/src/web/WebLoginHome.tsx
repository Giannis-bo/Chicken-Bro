import { webViewHref } from './web-routing'
import { useEffect, type ReactNode } from 'react'
import mascot from './assets/gu-gu-mascot.png'
import PoweredBy from '../components/PoweredBy'
import styles from './WebLoginHome.module.scss'

export default function WebLoginHome({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.add('web-login-fixed')
    document.body.classList.add('web-login-fixed')
    return () => {
      document.documentElement.classList.remove('web-login-fixed')
      document.body.classList.remove('web-login-fixed')
    }
  }, [])

  return (
    <main className={styles['home']}>
      <header className={styles['header']}>
        <a className={styles['brand']} href={webViewHref('chat')} aria-label="炸鸡队长首页">
          <img src={mascot} alt="" width="44" height="44" />
          <span>炸鸡队长<span className={styles['brandNote']}>CHICKENBRO</span></span>
        </a>
      </header>

      <div className={styles['layout']}>
        <section className={styles['hero']} aria-labelledby="home-title">
          <p className={styles['eyebrow']}><span /> 你的艾泽拉斯冒险搭档</p>
          <h1 id="home-title">开打之前，<br />先问<span>鸡哥。</span></h1>
          <p className={styles['intro']}>从一场战斗，到下一次提升。<br />聊清思路，让模拟帮你做选择。</p>
          <a className={styles['heroLink']} href="#qq-login" onClick={(event) => {
            event.preventDefault()
            document.getElementById('qq-login')?.focus({ preventScroll: true })
          }}>QQ 登录，和鸡哥聊聊 <span aria-hidden="true">↗</span></a>
          <div className={styles['mascotScene']} aria-hidden="true">
            <span className={styles['orbit']} />
            <span className={styles['hello']}>队长，等你开聊！</span>
            <img src={mascot} alt="" />
            <span className={styles['spark']}>✦</span>
          </div>
        </section>

        <aside id="qq-login" className={styles['login']} aria-label="QQ 登录" tabIndex={-1}>
          <div className={styles['loginHeading']}>
            <span className={styles['loginDot']} />
            <span>QQ 登录</span>
            <span className={styles['loginArrow']} aria-hidden="true">↙</span>
          </div>
          <h2>鸡哥已就位</h2>
          {children}
        </aside>
      </div>
      <PoweredBy />
    </main>
  )
}
