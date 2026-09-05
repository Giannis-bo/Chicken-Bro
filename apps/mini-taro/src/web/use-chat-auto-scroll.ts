import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'

export function useChatAutoScroll(
  list: RefObject<HTMLDivElement>, content: RefObject<HTMLDivElement>,
  conversation: string, sending: boolean, revision: unknown,
) {
  const following = useRef(true)
  const previous = useRef({ conversation, sending: false })
  const lastTop = useRef(0)
  const [paused, setPaused] = useState(false)
  const setFollowing = useCallback((value: boolean) => {
    following.current = value
    setPaused(!value)
  }, [])
  const selected = useCallback(() => {
    const selection = window.getSelection()
    return Boolean(list.current && selection && !selection.isCollapsed && selection.rangeCount
      && selection.getRangeAt(0).intersectsNode(list.current))
  }, [list])
  const scrollToBottom = useCallback(() => {
    const element = list.current
    if (!element) return
    element.scrollTop = element.scrollHeight
    lastTop.current = element.scrollTop
  }, [list])
  const follow = useCallback(() => {
    if (following.current && !selected()) scrollToBottom()
  }, [scrollToBottom, selected])
  const jumpToLatest = useCallback(() => {
    if (selected()) window.getSelection()?.removeAllRanges()
    setFollowing(true)
    scrollToBottom()
  }, [scrollToBottom, selected, setFollowing])

  useLayoutEffect(() => {
    if (previous.current.conversation !== conversation || (!previous.current.sending && sending)) {
      setFollowing(true)
    }
    previous.current = { conversation, sending }
    follow()
  }, [conversation, sending, revision, follow, setFollowing])

  useEffect(() => {
    const element = list.current
    const body = content.current
    if (!element || !body) return
    const onScroll = () => {
      const top = element.scrollTop
      const maximum = Math.max(0, element.scrollHeight - element.clientHeight)
      const clampedAtBottom = following.current && lastTop.current > maximum + 1 && top >= maximum - 1
      if (selected()) setFollowing(false)
      else if (top < lastTop.current - 1 && !clampedAtBottom) setFollowing(false)
      else if (maximum - top <= 32) setFollowing(true)
      lastTop.current = top
    }
    const onWheel = (event: WheelEvent) => { if (event.deltaY < 0) setFollowing(false) }
    const onKey = (event: KeyboardEvent) => {
      if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) setFollowing(false)
    }
    const onSelection = () => { if (selected()) setFollowing(false) }
    let touchY = 0
    const onTouchStart = (event: TouchEvent) => { touchY = event.touches[0]?.clientY ?? 0 }
    const onTouchMove = (event: TouchEvent) => {
      const y = event.touches[0]?.clientY ?? touchY
      if (y > touchY + 2) setFollowing(false)
      touchY = y
    }
    element.addEventListener('scroll', onScroll, { passive: true })
    element.addEventListener('wheel', onWheel, { passive: true })
    element.addEventListener('keydown', onKey)
    element.addEventListener('touchstart', onTouchStart, { passive: true })
    element.addEventListener('touchmove', onTouchMove, { passive: true })
    document.addEventListener('selectionchange', onSelection)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(follow)
    observer?.observe(body)
    observer?.observe(element)
    return () => {
      observer?.disconnect()
      element.removeEventListener('scroll', onScroll)
      element.removeEventListener('wheel', onWheel)
      element.removeEventListener('keydown', onKey)
      element.removeEventListener('touchstart', onTouchStart)
      element.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('selectionchange', onSelection)
    }
  }, [list, content, follow, selected, setFollowing])

  return { paused, jumpToLatest }
}
