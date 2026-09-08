import { createContext } from 'react'

export const MiniAccountContext = createContext<() => void>(() => undefined)
