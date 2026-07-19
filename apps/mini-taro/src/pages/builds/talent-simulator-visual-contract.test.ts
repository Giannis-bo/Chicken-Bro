import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const componentPath = resolve(process.cwd(), 'packages/design-system/src/components/TalentSimulatorComponents.tsx')
const stylePath = resolve(process.cwd(), 'packages/design-system/src/components/TalentSimulatorComponents.module.scss')
const modelPath = resolve(process.cwd(), 'apps/mini-taro/src/pages/builds/talent-simulator-model.ts')

describe('talent simulator legacy visual contract', () => {
  it('uses the real legacy pixel canvas, centered bounds renderer, and directed nodes', () => {
    const componentSource = readFileSync(componentPath, 'utf8')
    const styleSource = readFileSync(stylePath, 'utf8')
    const modelSource = readFileSync(modelPath, 'utf8')

    expect(modelSource).toContain('const readyGraphWidth = 350')
    expect(modelSource).toContain('const readyRowGap = 48')
    expect(modelSource).toContain('const readyNodeSize = 36')
    expect(modelSource).toContain('const linkArrowHead = 6')
    expect(modelSource).not.toContain('class: 1080')
    expect(modelSource).not.toContain('spec: 1080')
    expect(componentSource).toContain('data-role="talent-choice-frame"')
    expect(componentSource).toContain('data-arrow="end"')
    expect(componentSource).toContain('`${node.x}px`')
    expect(componentSource).toContain('`${stageWidth}px`')
    expect(componentSource).toContain('const graphViewportWidth = 350')
    expect(componentSource).toContain('const graphScale =')
    expect(componentSource).toContain('const planeLeft = (stageWidth - renderedBoundsWidth) / 2 - minNodeX * graphScale')
    expect(componentSource).not.toContain("componentStyle('choiceBadge')")
    expect(styleSource).toContain(".graphEdge[data-arrow='end']::after")
    expect(styleSource).toContain('.choiceFrame::after')
    expect(styleSource).toContain('.graphNodeChoice::before')
    expect(styleSource).toContain('.graphNodeChoice::after')
    expect(styleSource).toContain('border-right: 7px solid rgba(150, 150, 150, 0.72)')
    expect(styleSource).toContain('border-left: 7px solid rgba(150, 150, 150, 0.72)')
    expect(styleSource).toContain('width: 36px')
    expect(styleSource).toContain('height: 1px')
  })

  it('keeps a two-choice frame free of the generic rectangular status outline', () => {
    const styleSource = readFileSync(stylePath, 'utf8').replace(/\r\n/g, '\n')

    expect(styleSource).toContain(".graphNode[data-shape='choice'][data-state] {\n  box-shadow: none;\n}")
  })
})
