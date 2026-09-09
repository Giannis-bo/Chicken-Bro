import { useEffect, type PropsWithChildren } from 'react'
import WebApp from './web/WebApp'
import './app.scss'

export default function App({ children }: PropsWithChildren) {
  useEffect(() => {
    document.documentElement.classList.add('web-runtime-scroll')
    document.body.classList.add('web-runtime-scroll')
    return () => {
      document.documentElement.classList.remove('web-runtime-scroll')
      document.body.classList.remove('web-runtime-scroll')
    }
  }, [])
  return <><WebApp /><div className="web-page-mount">{children}</div></>
}
