import { useCallback, useEffect, useState } from 'react'

export type HelpSection = 'faq' | 'changelog'
export type HelpRevisions = Readonly<Record<HelpSection, string>>
const sections: HelpSection[] = ['faq', 'changelog']
export const helpReadKey = (section: HelpSection) => `chickenbro.help-read.v1.${section}`

function readSaved(): Record<HelpSection, string | null> {
  const saved: Record<HelpSection, string | null> = { faq: null, changelog: null }
  for (const section of sections) {
    try { saved[section] = window.localStorage.getItem(helpReadKey(section)) } catch { /* Storage can be unavailable. */ }
  }
  return saved
}

export function useHelpReadStatus(revisions: HelpRevisions) {
  const [saved, setSaved] = useState(readSaved)
  useEffect(() => {
    const restore = (event: StorageEvent) => {
      if (event.key === null || sections.some(section => helpReadKey(section) === event.key)) setSaved(readSaved())
    }
    window.addEventListener('storage', restore)
    return () => window.removeEventListener('storage', restore)
  }, [])
  const markRead = useCallback((section: HelpSection) => {
    const revision = revisions[section]
    setSaved(previous => previous[section] === revision ? previous : { ...previous, [section]: revision })
    try { window.localStorage.setItem(helpReadKey(section), revision) } catch { /* Keep the in-memory read state. */ }
  }, [revisions])
  return {
    unread: { faq: saved.faq !== revisions.faq, changelog: saved.changelog !== revisions.changelog },
    markRead,
  }
}
