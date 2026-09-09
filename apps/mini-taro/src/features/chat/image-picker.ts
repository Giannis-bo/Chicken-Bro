export async function chooseChatImages(count: number): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/png,image/jpeg'
    input.multiple = true
    input.oncancel = () => resolve([])
    input.onchange = () => {
      const files = Array.from(input.files ?? [])
      void readChatImageFiles(files, count).then(resolve, reject)
    }
    input.click()
  })
}

export async function readChatImageFiles(files: readonly File[], count: number): Promise<string[]> {
  if (files.length > count) throw new Error('每条消息最多三张图片，请先移除部分图片')
  if (files.some(file => !['image/png', 'image/jpeg'].includes(file.type))) throw new Error('请选择 PNG/JPEG 图片')
  if (files.some(file => file.size > 5242880)) throw new Error('每张图片不超过 5 MiB')
  return Promise.all(files.map(file => new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('图片读取失败，请重试'))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })))
}
