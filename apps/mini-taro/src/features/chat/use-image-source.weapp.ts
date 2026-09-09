import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'

const prefix = 'chickenbro-preview-'
let sequence = 0
let cleanup: Promise<void> | undefined
function clearPreviousPreviews(): Promise<void> {
  cleanup ??= new Promise(resolve => {
    const fs = Taro.getFileSystemManager()
    fs.readdir({dirPath: Taro.env.USER_DATA_PATH ?? '', success: result => {
      const files = result.files.filter(name => name.startsWith(prefix))
      void Promise.all(files.map(name => new Promise<void>(done => {
        fs.unlink({filePath: Taro.env.USER_DATA_PATH + '/' + name, complete: () => done()})
      }))).then(() => resolve())
    }, fail: () => resolve()})
  })
  return cleanup
}
// Only a short private sandbox path crosses the Mini setData bridge. The file is
// temporary for this mounted preview and removed at unmount; restart clears any
// files left by a terminated process. It is never used as cached chat history.
export function useImageSource(dataUrl: string) {
  const [source, setSource] = useState('')
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const fs = Taro.getFileSystemManager()
    const path = Taro.env.USER_DATA_PATH + '/' + prefix + Date.now() + '-' + (++sequence)
      + (dataUrl.startsWith('data:image/png;') ? '.png' : '.jpg')
    const remove = () => fs.unlink({filePath: path, fail: () => undefined})
    setSource('')
    setFailed(false)
    void clearPreviousPreviews().then(() => {
      if (!active) return
      fs.writeFile({filePath: path, data: dataUrl.slice(dataUrl.indexOf(',') + 1), encoding: 'base64',
        success: () => { if (active) setSource(path); else remove() }, fail: () => { if (active) setFailed(true) }})
    })
    return () => { active = false; remove() }
  }, [dataUrl, attempt])
  return {source, failed, retry: () => setAttempt(value => value + 1)}
}
