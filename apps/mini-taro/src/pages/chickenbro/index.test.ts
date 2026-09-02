import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'


function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('formal Chickenbro Mini route', () => {
  it('registers exactly the approved five routes', () => {
    const config = source('apps/mini-taro/src/app.config.ts')
    const pageBlock = config.match(/pages:\s*\[([\s\S]*?)\]/u)?.[1] ?? ''
    const pages = [...pageBlock.matchAll(/'([^']+)'/gu)].map((match) => match[1])

    expect(pages).toEqual([
      'pages/chickenbro/index',
      'pages/simc/index',
      'pages/simc/tasks',
      'pages/simc/task-detail',
      'pages/auth/web-login-confirm',
    ])
  })

  it('uses the formal session and server-backed Chat model without legacy simulator calls', () => {
    const page = source('apps/mini-taro/src/pages/chickenbro/index.tsx')
    expect(page).toContain('MiniSessionStore')
    expect(page).toContain('ChatModel')
    expect(page).toContain('.load()')
    expect(page).toContain('.send(')
    expect(page).toContain('重新登录')
    expect(page).not.toContain('wowApi.simulator')
    expect(page).not.toContain('prototype')
  })
})
