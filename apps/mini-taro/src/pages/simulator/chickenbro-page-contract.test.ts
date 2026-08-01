import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Captain archive page contract', () => {
  it('returns directly to the Captain tab instead of relying on page-stack history', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/chickenbro.tsx',
    ), 'utf8')

    expect(source).toMatch(/onBack=\{\(\) => void Taro\.switchTab\(\{ url: '\/pages\/simulator\/simulator' \}\)\}/u)
  })
})
