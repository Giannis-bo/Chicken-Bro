import { transformSync } from '@babel/core'
import { describe, expect, it } from 'vitest'

// eslint-disable-next-line @typescript-eslint/no-require-imports
const dataSelectorMarkers = require('../../config/babel-data-selector-markers.cjs')

function transform(source: string): string {
  return transformSync(source, {
    babelrc: false,
    configFile: false,
    filename: 'fixture.tsx',
    parserOpts: { plugins: ['jsx', 'typescript'] },
    plugins: [dataSelectorMarkers],
  })?.code ?? ''
}

describe('babel-data-selector-markers', () => {
  it('adds matching markers without discarding the existing class name', () => {
    const result = transform(`const view = <View className={styles.card} data-state={state} data-role="summary" />`)

    expect(result).toContain('selectorClass(styles.card')
    expect(result).toContain('dataSelectorClass("state", state)')
    expect(result).toContain('dataSelectorClass("role", "summary")')
  })

  it('creates a class name for static and boolean data attributes', () => {
    const result = transform(`const view = <View data-disabled="true" data-active />`)

    expect(result).toContain('selectorClass(null')
    expect(result).toContain('dataSelectorClass("disabled", "true")')
    expect(result).toContain('dataSelectorClass("active", true)')
  })

  it('does not alter elements without data attributes', () => {
    const result = transform(`const view = <View className="plain" />`)

    expect(result).not.toContain('selector-markers')
    expect(result).toContain('className="plain"')
  })
})
