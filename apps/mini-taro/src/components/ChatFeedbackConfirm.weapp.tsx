import Taro from '@tarojs/taro'
import { useEffect, useRef } from 'react'

interface Props {
  resolved: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ChatFeedbackConfirm(props: Props) {
  const latest = useRef(props)
  latest.current = props
  useEffect(() => {
    let active = true
    void Taro.showModal({
      title: `确认「${latest.current.resolved ? '已解决' : '未解决'}」反馈？`,
      content: '您的反馈会让鸡哥变得更好。',
      confirmText: '确认', cancelText: '取消',
    }).then(result => {
      if (active) { if (result.confirm) latest.current.onConfirm(); else latest.current.onCancel() }
    }).catch(() => { if (active) latest.current.onCancel() })
    return () => { active = false }
  }, [])
  return null
}
