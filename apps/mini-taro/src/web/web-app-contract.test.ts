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

    expect(appSource).toContain('Taro.ENV_TYPE.WEB')
    expect(appSource).toContain('<WebApp />')
    expect(appSource).toContain('<AppTabBar />')
    expect(webSource).not.toContain('AppTabBar')
    expect(webSource).toContain('webAuth.me()')
    expect(webSource).toContain('webAuth.createWebLoginSession')
    expect(webSource).toContain('webAuth.statusWebLoginSession')
    expect(webSource).toContain('webAuth.exchangeWebLoginSession')
    expect(webSource).toContain('WebShell')
    expect(webSource).toContain('readWebCsrfCookie')
    expect(webSource).toContain('createSession(true)')
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

  it('makes formal QR login the only Web entry and keeps credentials separated', () => {
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')

    for (const copy of [
      '使用微信小程序登录',
      '请使用电脑或另一台设备展示二维码',
      '使用小程序确认',
      '登录已确认，正在建立 Web 会话',
    ]) {
      expect(webSource).toContain(copy)
    }
    expect(webSource).toContain('credentials')
    expect(webSource).toContain('WebShell')
    expect(webSource).not.toContain('wowApi.auth')
    expect(webSource).not.toContain('/api/auth/wechat-login')
    expect(webSource).not.toContain('localStorage')
    expect(webSource).not.toContain('browserVerifier=')
    expect(webSource).not.toMatch(/PrototypePanel|prototypeClient|formalLoginVisible|返回 Web 原型|demo owner/iu)
  })

  it('pins the H5 QR image content to the full QR frame', () => {
    const webStyle = read('apps/mini-taro/src/web/WebApp.module.scss')

    expect(webStyle).toMatch(/\.qrImage\s*>\s*img\s*\{[\s\S]*position:\s*absolute[\s\S]*top:\s*0[\s\S]*right:\s*0[\s\S]*bottom:\s*0[\s\S]*left:\s*0[\s\S]*object-fit:\s*contain/u)
  })

  it('uses the independent /api H5 development proxy while retaining /wow-api', () => {
    const configSource = read('apps/mini-taro/config/index.ts')
    expect(configSource).toContain("'/api'")
    expect(configSource).toContain('http://127.0.0.1:8790')
    expect(configSource).toContain("'/wow-api'")
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
