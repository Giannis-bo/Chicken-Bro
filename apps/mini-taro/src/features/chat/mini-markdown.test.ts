import { describe, expect, it } from 'vitest'
import { miniMarkdownBlocks, miniInlineTokens } from './mini-markdown'

describe('Mini reply formatting', () => {
  it('turns a timeline table into labelled rows without dropping escaped pipes', () => {
    expect(miniMarkdownBlocks('| 时间 | 发生了什么 |\n|---|---|\n| **20:54** | 嘲讽\\|尾王 |')).toEqual([
      { kind: 'table', headers: ['时间', '发生了什么'], rows: [['**20:54**', '嘲讽|尾王']] },
    ])
  })
  it('keeps incomplete streaming text and code literal', () => {
    expect(miniMarkdownBlocks('## 结论\n**尚未结束\n\n```\n<script>x</script>\n**原文**')).toEqual([
      { kind: 'heading', content: '结论' },
      { kind: 'paragraph', content: '**尚未结束' },
      { kind: 'code', content: '<script>x</script>\n**原文**' },
    ])
  })
  it('formats emphasis and accepts only HTTP links for clipboard actions', () => {
    expect(miniInlineTokens('**结论** [日志](https://cn.warcraftlogs.com/reports/a)')).toEqual([
      { kind: 'bold', content: '结论' }, { kind: 'text', content: ' ' },
      { kind: 'link', content: '日志', url: 'https://cn.warcraftlogs.com/reports/a' },
    ])
    expect(miniInlineTokens('[危险](javascript:alert(1)) <img src=x>')).toEqual([
      { kind: 'text', content: '[危险](javascript:alert(1)) <img src=x>' },
    ])
  })
})
