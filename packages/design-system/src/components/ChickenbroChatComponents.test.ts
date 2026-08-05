import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const componentSource = readFileSync(resolve(
  process.cwd(),
  'packages/design-system/src/components/ChickenbroChatComponents.tsx',
), 'utf8')

describe('Chickenbro evidence outcome marker', () => {
  it('renders a partial marker without exposing source internals', () => {
    expect(componentSource).toContain('data-role="chickenbro-evidence-outcome"')
    expect(componentSource).toContain("partial: '部分证据'")
    expect(componentSource).not.toContain('source:raiderio-strength:v1')
  })
})
