import { useState } from 'react'

export interface TrustedMediaLoadState {
  failed: boolean
  loaded: boolean
  visible: boolean
}

export function resolveTrustedMediaLoadState(
  url: string,
  loadedUrl: string,
  failedUrl: string,
): TrustedMediaLoadState {
  const loaded = Boolean(url) && loadedUrl === url
  const failed = Boolean(url) && failedUrl === url
  return {
    failed,
    loaded,
    visible: loaded && !failed,
  }
}

/**
 * Tracks native image events by URL instead of resetting booleans in an effect.
 * On a warm WeChat image cache, `onLoad` can arrive before the effect for the
 * current URL; resetting booleans there would hide a successfully loaded image.
 */
export function useTrustedMediaLoadState(url: string) {
  const [loadedUrl, setLoadedUrl] = useState('')
  const [failedUrl, setFailedUrl] = useState('')
  const state = resolveTrustedMediaLoadState(url, loadedUrl, failedUrl)

  return {
    ...state,
    onError: () => {
      setFailedUrl(url)
      setLoadedUrl((current) => current === url ? '' : current)
    },
    onLoad: () => {
      setLoadedUrl(url)
      setFailedUrl((current) => current === url ? '' : current)
    },
  }
}
