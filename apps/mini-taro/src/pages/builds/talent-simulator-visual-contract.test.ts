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
    expect(componentSource).toContain('function talentGraphRpx(value: number): string')
    expect(componentSource).toContain('return `${value * (750 / 390)}rpx`')
    expect(componentSource).toContain('left: talentGraphRpx(node.x)')
    expect(componentSource).toContain('width: talentGraphRpx(stageWidth)')
    expect(componentSource).toContain('const graphViewportWidth = 350')
    expect(componentSource).toContain('const graphViewportHeight = 461')
    expect(componentSource).toContain('const graphInset = 8')
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

  it('keeps the expanded tree inside a vertically scrollable viewport with safe top and bottom reach', () => {
    const componentSource = readFileSync(componentPath, 'utf8')

    expect(componentSource).toContain('const targetContentHeight = graphViewportHeight - graphInset * 2')
    expect(componentSource).toContain(`const graphScale = Math.min(
    1,
    targetContentWidth / nodeBoundsWidth,
    allowVerticalOverflow ? 1 : targetContentHeight / nodeBoundsHeight,
  )`)
    expect(componentSource).toContain('allowVerticalOverflow?: boolean')
    expect(componentSource).toContain('allowVerticalOverflow = false')
    expect(componentSource).toContain('const planeTop = (stageHeight - renderedBoundsHeight) / 2 - minNodeY * graphScale')
    expect(componentSource).toContain('const graphVerticalScrollPadding = 24')
    expect(componentSource).toContain('renderedBoundsHeight + graphVerticalScrollPadding * 2')
    expect(componentSource).toContain('scrollY={stageHeight > graphViewportHeight}')
    expect(componentSource).toContain('showScrollbar={stageHeight > graphViewportHeight}')
    expect(componentSource).not.toContain('scrollY={false}')
  })
})
