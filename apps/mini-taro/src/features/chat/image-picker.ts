export async function chooseChatImages(count: number): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/png,image/jpeg'
    input.multiple = true
    input.oncancel = () => resolve([])
    input.onchange = () => {
      const files = Array.from(input.files ?? [])
      if (files.length > count || files.some(file => !['image/png', 'image/jpeg'].includes(file.type) || file.size > 5242880)) {
        reject(new Error('最多三张图片，每张 PNG/JPEG 不超过 5 MiB'))
        return
      }
      void Promise.all(files.map(file => new Promise<string>((done, fail) => {
        const reader = new FileReader()
        reader.onerror = () => fail(new Error('图片读取失败'))
        reader.onload = () => done(String(reader.result))
        reader.readAsDataURL(file)
      }))).then(resolve, reject)
    }
    input.click()
  })
}
