import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { tabBarItems } from '../../tab-bar-items'

const sourcePath = resolve(process.cwd(), 'apps/mini-taro/src/pages/auth/web-login-confirm.tsx')

describe('mini-program Web login confirmation page', () => {
  it('uses Taro login and requires an explicit confirmation action', () => {
    const source = readFileSync(sourcePath, 'utf8')
    expect(source).toContain('Taro.login')
    expect(source).toContain('exchangeMiniCode')
    expect(source).toContain('confirmMiniWebLogin')
    expect(source).toContain('确认登录')
    expect(source).toContain('WEB_LOGIN_ALREADY_CONSUMED')
    expect(source).not.toContain('WEB_LOGIN_ALREADY_EXCHANGED')
    expect(source).not.toContain('wx.getStorage')
    expect(source).not.toContain('WOW_WECHAT_SECRET')
    expect(source).not.toContain('openid')
    expect(source).not.toContain('unionid')
    expect(source).not.toContain('session_key')
  })

  it('is not a tab route or active product visual target', () => {
    expect(tabBarItems.map((item) => item.pagePath)).not.toContain('pages/auth/web-login-confirm')
    expect(readFileSync(resolve(process.cwd(), 'apps/mini-taro/src/pages/auth/web-login-confirm.config.ts'), 'utf8'))
      .toContain('navigationStyle')
  })
})
