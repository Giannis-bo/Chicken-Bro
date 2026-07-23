import Taro from '@tarojs/taro'

export async function chooseActionSheetEntry<T>(
  items: readonly T[],
  labelFor: (item: T) => string,
): Promise<T | null> {
  for (let offset = 0; offset < items.length; offset += 5) {
    const pageItems = items.slice(offset, offset + 5)
    const hasMore = offset + pageItems.length < items.length
    try {
      const choice = await new Promise<{ tapIndex: number }>((resolve, reject) => {
        const request = Taro.showActionSheet({
          itemList: [...pageItems.map(labelFor), ...(hasMore ? ['更多选项…'] : [])],
          success: ({ tapIndex }) => resolve({ tapIndex }),
          fail: reject,
        })
        if (request && typeof request.then === 'function') {
          void request.then(({ tapIndex }) => resolve({ tapIndex })).catch(reject)
        }
      })
      if (hasMore && choice.tapIndex === pageItems.length) continue
      return pageItems[choice.tapIndex] ?? null
    } catch {
      return null
    }
  }
  return null
}
