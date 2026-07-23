import { describe, expect, it, vi } from 'vitest'

const { showActionSheet } = vi.hoisted(() => ({ showActionSheet: vi.fn() }))

vi.mock('@tarojs/taro', () => ({
  default: { showActionSheet },
}))

import { chooseActionSheetEntry } from './action-sheet'

describe('chooseActionSheetEntry', () => {
  it('uses the native success callback when the action-sheet call does not return a promise', async () => {
    const selected = { id: 'community-winner' }
    showActionSheet.mockImplementationOnce(({ success }) => {
      success({ tapIndex: 0 })
      return undefined
    })

    await expect(chooseActionSheetEntry([selected], () => '社区高端玩家模板')).resolves.toBe(selected)
  })

  it('uses the returned promise when the native callback is not fired', async () => {
    const selected = { id: 'community-winner' }
    showActionSheet.mockResolvedValueOnce({ tapIndex: 0 })

    await expect(chooseActionSheetEntry([selected], () => '社区高端玩家模板')).resolves.toBe(selected)
  }, 200)
})
