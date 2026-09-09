import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
export default function ChatImageOverlay({children}: {children: ReactNode}) {
  return createPortal(children, document.body)
}
