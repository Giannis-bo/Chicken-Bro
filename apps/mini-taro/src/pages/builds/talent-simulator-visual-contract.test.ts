import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const componentPath = resolve(process.cwd(), 'packages/design-system/src/components/TalentSimulatorComponents.tsx')
const stylePath = resolve(process.cwd(), 'packages/design-system/src/components/TalentSimulatorComponents.module.scss')
const modelPath = resolve(process.cwd(), 'apps/mini-taro/src/pages/builds/talent-simulator-model.ts')

describe('talent simulator legacy visual contract', () => {
  it('uses the legacy rpx canvas and directed-node renderer instead of a compressed bounding-box transform', () => {
    const componentSource = readFileSync(componentPath, 'utf8')
    const styleSource = readFileSync(stylePath, 'utf8')
    const modelSource = readFileSync(modelPath, 'utf8')

    expect(modelSource).toContain('const talentGridWidth = 660')
    expect(modelSource).toContain('const talentNodeRadius = 32')
    expect(modelSource).toContain('const linkArrowHead = 12')
    expect(modelSource).not.toContain('const readyGraphWidth = 350')
    expect(componentSource).toContain('data-role="talent-choice-frame"')
    expect(componentSource).toContain('data-arrow="end"')
    expect(componentSource).toContain('`${node.x}rpx`')
    expect(componentSource).not.toContain('const graphScale =')
    expect(componentSource).not.toContain("componentStyle('choiceBadge')")
    expect(styleSource).toContain(".graphEdge[data-arrow='end']::after")
    expect(styleSource).toContain('.choiceFrame::after')
    expect(styleSource).toContain('.graphNodeChoice::before')
    expect(styleSource).toContain('.graphNodeChoice::after')
    expect(styleSource).toContain('border-right: 10rpx solid rgba(150, 150, 150, 0.72)')
    expect(styleSource).toContain('border-left: 10rpx solid rgba(150, 150, 150, 0.72)')
    expect(styleSource).toContain('width: 64rpx')
    expect(styleSource).toContain('height: 5rpx')
  })

  it('keeps a two-choice frame free of the generic rectangular status outline', () => {
    const styleSource = readFileSync(stylePath, 'utf8')

    expect(styleSource).toContain(".graphNode[data-shape='choice'][data-state] {\n  box-shadow: none;\n}")
  })
})
