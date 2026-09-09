import Taro from '@tarojs/taro'

export async function chooseChatImages(count: number): Promise<string[]> {
  const result = await Taro.chooseMedia({ count, mediaType: ['image'], sizeType: ['original'] })
  return Promise.all(result.tempFiles.map(async file => {
    if (file.size > 5242880) throw new Error('每张图片不超过 5 MiB')
    const info = await Taro.getImageInfo({ src: file.tempFilePath })
    const kind = info.type.toLowerCase()
    if (!['png', 'jpeg', 'jpg'].includes(kind)) throw new Error('请选择 PNG/JPEG 图片')
    const base64 = await new Promise<string>((resolve, reject) => {
      Taro.getFileSystemManager().readFile({ filePath: file.tempFilePath, encoding: 'base64',
        success: result => resolve(String(result.data)), fail: reject })
    })
    return `data:image/${kind === 'png' ? 'png' : 'jpeg'};base64,${base64}`
  }))
}
