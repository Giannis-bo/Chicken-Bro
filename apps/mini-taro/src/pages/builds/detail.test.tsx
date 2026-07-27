import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const pageSource = readFileSync(resolve(
  process.cwd(),
  'apps/mini-taro/src/pages/builds/detail.tsx',
), 'utf8')

describe('gear detail enhancement capability presentation', () => {
  it('renders only canonical capability labels and blocks unavailable categories', () => {
    expect(pageSource).toContain('value: group.availabilityLabel')
    expect(pageSource).toContain('if (group?.disabled) return')
    expect(pageSource).not.toContain('artifactId')
    expect(pageSource).not.toContain('canonicalEvidence')
    expect(pageSource).not.toContain('workerStatus')
    expect(pageSource).not.toContain('rootCode')
  })
})
