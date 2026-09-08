import { resolveWebTheme, type WebThemeId } from './web-themes'
import styles from './WebThemeArt.module.scss'

export default function WebThemeArt({ themeId }: { themeId: WebThemeId }) {
  const theme = resolveWebTheme(themeId)
  return <div className={styles['art']} aria-hidden="true" data-theme-art={theme.id}
    style={{ backgroundImage: `url("${theme.image}")` }} />
}
