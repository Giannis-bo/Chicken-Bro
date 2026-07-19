import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('simulator home page interaction contract', () => {
  it('mounts a loading-safe local new-topic reset without a backend write', () => {
    const source = readFileSync(resolve(
      process.cwd(),
      'apps/mini-taro/src/pages/simulator/simulator.tsx',
    ), 'utf8')

    expect(source).toContain('SimulatorCaptainAction,')
    expect(source).toContain('const resetTopic = () => {')
    expect(source).toContain('setMessages(initialSimulatorHomeMessages())')
    expect(source).toContain("setDraft('')")
    expect(source).toContain("setSessionId('')")
    expect(source).toContain("setInputState('ready')")
    expect(source).toContain("setLastSubmitted('')")
    expect(source).toContain("disabled={inputState === 'loading'}")
    expect(source).toContain('onReset={resetTopic}')

    const resetBody = /const resetTopic = \(\) => \{([\s\S]*?)\n\s{2}\}/u.exec(source)?.[1] ?? ''
    expect(resetBody).not.toContain('wowApi')
  })

  it('allocates the target-width captain action in a centered PageFrame header', () => {
    const ownerStyles = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/owners.module.scss',
    ), 'utf8')
    const simulatorStyles = readFileSync(resolve(
      process.cwd(),
      'packages/design-system/src/components/SimulatorHomeComponents.module.scss',
    ), 'utf8')

    expect(ownerStyles).toMatch(/\.pageFrameOwner\[data-variant='simulator-home'\] \.pageFrameHeader\s*\{[^}]*grid-template-columns:\s*90px minmax\(0, 1fr\) 90px;/su)
    expect(ownerStyles).toMatch(/\.pageFrameOwner\[data-variant='simulator-home'\] \.pageFrameHeaderLeading\s*\{[^}]*grid-column:\s*2;/su)
    expect(ownerStyles).toMatch(/\.pageFrameOwner\[data-variant='simulator-home'\] \.pageFrameHeaderAction\s*\{[^}]*grid-column:\s*3;/su)
    expect(ownerStyles).toMatch(/\.pageFrameOwner\[data-variant='simulator-home'\] \.pageFrameTitleText\s*\{[^}]*text-align:\s*center;/su)
    expect(simulatorStyles).toMatch(/\.captainAction\s*\{[^}]*width:\s*90px;/su)
    expect(ownerStyles).toMatch(/@media \(max-width: 350px\)\s*\{[\s\S]*?\.pageFrameOwner\[data-variant='simulator-home'\] \.pageFrameHeader\s*\{[^}]*grid-template-columns:\s*36px minmax\(0, 1fr\) 36px;/su)
    expect(simulatorStyles).toMatch(/@media \(max-width: 350px\)\s*\{[\s\S]*?\.captainAction\s*\{[^}]*width:\s*36px;[\s\S]*?\.captainActionCopy\s*\{[^}]*display:\s*none;/su)
  })
})
