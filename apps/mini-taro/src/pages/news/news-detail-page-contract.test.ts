import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('news detail terminal recovery contract', () => {
  it('renders owned recovery actions for error, blocked, and missing states', () => {
    const componentSource = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/NewsDetailComponents.tsx',
    ), 'utf8')

    expect(componentSource).toContain("['error', 'blocked', 'missing'].includes(mode)")
    expect(componentSource).not.toContain("const showAction = Boolean(actionLabel && onAction && mode === 'error')")
  })
})
