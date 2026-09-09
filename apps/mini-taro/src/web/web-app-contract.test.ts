import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function read(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('Chickenbro Web shell contract', () => {
  it('composes a H5-only shell without the mini-program tab navigation', () => {
    const appSource = read('apps/mini-taro/src/app.tsx')
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')

    expect(appSource).toContain('<WebApp />')
    expect(appSource).not.toContain('AppTabBar')
    expect(webSource).not.toContain('AppTabBar')
    expect(webSource).toContain('authClient.me()')
    expect(webSource).toContain('authClient.createQqLogin()')
    expect(webSource).not.toMatch(/createWebLoginSession|statusWebLoginSession|exchangeWebLoginSession/)
    expect(webSource).toContain('WebShell')
    expect(webSource).toContain('readWebCsrfCookie')
    expect(webSource).toContain('navigateToProvider')
  })

  it('keeps the Taro H5 page mount alive behind the standalone shell', () => {
    const appSource = read('apps/mini-taro/src/app.tsx')

    expect(appSource).toContain('<WebApp />')
    expect(appSource).toContain('web-page-mount')
    expect(appSource).toMatch(/web-page-mount[\s\S]*\{children\}/u)
  })

  it('releases the Taro H5 viewport lock so the standalone Web shell can scroll', () => {
    const appSource = read('apps/mini-taro/src/app.tsx')
    const appStyle = read('apps/mini-taro/src/app.scss')

    expect(appSource).toContain('web-runtime-scroll')
    expect(appSource).toMatch(/document\.body\.classList\.add\(['"]web-runtime-scroll['"]\)/u)
    expect(appStyle).toMatch(/html\.web-runtime-scroll[\s\S]*overflow-y:\s*auto\s*!important/u)
    expect(appStyle).toContain('body.web-runtime-scroll #app')
    expect(appStyle).toMatch(/taro-tabbar__panel[\s\S]*overflow:\s*visible\s*!important/u)
    expect(appStyle).toContain('max-height: none !important')
  })

  it('makes explicit QQ login the only Web entry and keeps credentials separated', () => {
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')

    expect(webSource).toContain('credentials')
    expect(webSource).toContain('QQ登录')
    expect(webSource).not.toMatch(/qrDataUrl|扫码|微信/)
    expect(webSource).toContain('WebShell')
    expect(webSource).not.toContain('wowApi.auth')
    expect(webSource).not.toContain('/api/auth/wechat-login')
    expect(webSource).not.toContain('localStorage')
    expect(webSource).not.toContain('browserVerifier=')
    expect(webSource).not.toMatch(/PrototypePanel|prototypeClient|formalLoginVisible|返回 Web 原型|demo owner/iu)
  })

  it('renders the official QQ mark without referrer data', () => {
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')
    expect(webSource).toContain('Connect_logo_1.png')
    expect(webSource).toContain('referrerPolicy="no-referrer"')
    expect(webSource).not.toContain('<Image')
  })

  it('uses only the formal same-origin /api development proxy', () => {
    const configSource = read('apps/mini-taro/config/index.ts')
    expect(configSource).toContain("'/api'")
    expect(configSource).toContain('http://127.0.0.1:8790')
    expect(configSource).not.toContain("'/wow-api'")
    expect(configSource).not.toContain('WOW_NEWS_API_BASE_URL')
    expect(configSource).not.toContain('124.223.51.33')
  })

  it('exposes only the two shared server-backed business views after login', () => {
    const shellSource = read('apps/mini-taro/src/web/WebShell.tsx')
    const chatSource = read('apps/mini-taro/src/web/WebChatView.tsx')
    const simcSource = read('apps/mini-taro/src/web/WebSimcView.tsx')

    expect(shellSource).toContain('WebChatView')
    expect(shellSource).toContain('WebSimcView')
    expect(shellSource).toContain('队长')
    expect(shellSource).toContain('SimC')
    expect(chatSource).toContain('ChatModel')
    expect(simcSource).toContain('SimcModel')
    expect(`${shellSource}\n${chatSource}\n${simcSource}`).not.toMatch(
      /news|builds|gear resolver|talent catalog|prototype/iu,
    )
  })
})
