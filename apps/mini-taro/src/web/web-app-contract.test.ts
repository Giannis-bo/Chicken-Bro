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

  it('makes the QR trust boundary and recovery states visible in the first viewport', () => {
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')

    for (const copy of [
      '使用微信小程序登录',
      '请使用电脑或另一台设备展示二维码',
      '使用小程序确认',
      '登录已确认，正在建立 Web 会话',
      '队长',
      'SimC',
    ]) {
      expect(webSource).toContain(copy)
    }
    expect(webSource).toContain('credentials')
    expect(webSource).not.toContain('wowApi.auth')
    expect(webSource).not.toContain('/api/auth/wechat-login')
    expect(webSource).not.toContain('localStorage')
    expect(webSource).not.toContain('browserVerifier=')
  })

  it('uses the independent /api H5 development proxy while retaining /wow-api', () => {
    const configSource = read('apps/mini-taro/config/index.ts')
    expect(configSource).toContain("'/api'")
    expect(configSource).toContain('http://127.0.0.1:8790')
    expect(configSource).toContain("'/wow-api'")
  })

  it('lands on the isolated prototype and keeps formal QR auth opt-in', () => {
    const webSource = read('apps/mini-taro/src/web/WebApp.tsx')
    const prototypeSource = read('apps/mini-taro/src/web/PrototypePanel.tsx')

    expect(webSource).toContain('PrototypePanel')
    expect(webSource).toContain('formalLoginVisible')
    expect(webSource).toContain('prototypeClient')
    expect(prototypeSource).toContain('data-prototype-auth-storage="sessionStorage-only"')
    expect(prototypeSource).toContain('原生 Codex')
    expect(prototypeSource).toContain('没有切换到其他模型')
  })

  it('explains source blockers instead of hiding the reason behind raw codes', () => {
    const prototypeSource = read('apps/mini-taro/src/web/PrototypePanel.tsx')

    expect(prototypeSource).toContain('CHARACTER_LEVEL_MISSING')
    expect(prototypeSource).toContain('prototype_max_level')
    expect(prototypeSource).toContain('按满级')
    expect(prototypeSource).not.toContain('snapshot.blockers.slice(0, 5)')
  })
})
