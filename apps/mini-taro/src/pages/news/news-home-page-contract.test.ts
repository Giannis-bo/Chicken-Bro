import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('news home favorite action contract', () => {
  it('hydrates, renders, persists, and announces the local home favorite state', () => {
    const pageSource = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/news/news.tsx',
    ), 'utf8')
    const pageFrameSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/PageFrame.tsx',
    ), 'utf8')

    expect(pageSource).toContain('useState(() => wowApi.news.isHomeFavorite())')
    expect(pageSource).toContain('homeFavorite,')
    expect(pageSource).not.toContain('homeFavorite: false')
    expect(pageSource).toContain('wowApi.news.setHomeFavorite(next)')
    expect(pageSource).toContain("title: next ? '已收藏资讯首页' : '已取消收藏'")
    expect(pageSource).toContain('rightAction={<PageFrameFavoriteAction')
    expect(pageFrameSource).toContain("dataRole=\"news-home-favorite\"")
    expect(pageFrameSource).toContain("selected ? 'news-favorite-control.selected' : 'news-favorite-control.default'")
    expect(pageFrameSource).toContain('slotId="asset_slot.news-favorite-control"')
  })

  it('locks the overall page scroll without removing pull-to-refresh', () => {
    const pageSource = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/news/news.tsx',
    ), 'utf8')
    const pageConfigSource = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/news/news.config.ts',
    ), 'utf8')

    expect(pageConfigSource).toMatch(/disableScroll:\s*true/)
    expect(pageConfigSource).toMatch(/enablePullDownRefresh:\s*true/)
    expect(pageSource).toContain('<AppShell bodyScrollable={false} tabRoot>')
  })
})
